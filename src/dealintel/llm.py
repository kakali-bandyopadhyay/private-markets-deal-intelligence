"""Optional model mode: the model phrases answers from retrieved passages only.

- The no-key mode (qa.py) stays the default and is what the tests and the reproducible results use.
- The model gets a fixed evidence pack (passage IDs and text) and must return structured claims with passage IDs.
- Citation validation then rejects any claim with a missing passage ID or an ID outside the evidence pack. This is
  citation validation, not fact verification; whether a passage supports a claim is checked in the evaluation.
- The model never selects deals, resolves conflicts or approves the IC memo: if it answers as if sources agree where
  the deterministic check found a conflict, the conflict is restored.
- Spend is capped per run (data/model_config.json); the run stops before a call that could exceed the cap.
- The API key is read from the environment or a git-ignored .env file and is never printed or logged.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from . import qa
from .data import ROOT, latest_date
from .search import search

SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["status", "claims"],
    "properties": {
        "status": {"type": "string", "enum": ["SUPPORTED", "CONFLICTED", "CHANGED", "INSUFFICIENT"]},
        "claims": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["text", "passage_ids"],
            "properties": {"text": {"type": "string"}, "passage_ids": {"type": "array", "items": {"type": "string"}}}}},
    },
}
INSTRUCTIONS = """You answer due-diligence questions for a private-markets deal team using ONLY the passages provided.
Rules:
- Every claim must list the passage_ids it comes from. Use only IDs from the list given. No outside knowledge.
- If the passages do not answer the question, return status INSUFFICIENT and no claims.
- If passages give different values for the same thing, return CONFLICTED with one claim per value. Do not choose.
- If a passage is marked SUPERSEDED and the question is about a change, return CHANGED and say which value replaced which.
- Do not recommend investment decisions, approve anything or judge which source is right.
Keep each claim to one sentence."""


class BudgetExceeded(RuntimeError):
    pass


class ModelError(RuntimeError):
    pass


def config() -> dict:
    return json.loads((ROOT / "data" / "model_config.json").read_text(encoding="utf-8"))


def api_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("OPENAI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return key or None


class Budget:
    def __init__(self, cfg: dict, max_usd: float | None = None):
        self.cfg, self.max = cfg, max_usd if max_usd is not None else cfg["max_cost_usd_per_run"]
        self.spent, self.calls = 0.0, 0

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.cfg["price_usd_per_1m_input"] + tokens_out * self.cfg["price_usd_per_1m_output"]) / 1e6

    def reserve(self, prompt_chars: int) -> None:
        worst = self.cost(prompt_chars // 3 + 50, self.cfg["max_output_tokens"])
        if self.spent + worst > self.max:
            raise BudgetExceeded(f"next call could cost up to ${worst:.4f}; spent ${self.spent:.4f} of the ${self.max:.2f} cap")

    def record(self, usage: dict) -> None:
        self.calls += 1
        self.spent += self.cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0))


def openai_client(key: str, cfg: dict):
    """Returns call(payload) -> response dict, using the Responses API over HTTPS (no SDK dependency)."""
    def call(payload: dict) -> dict:
        req = urllib.request.Request("https://api.openai.com/v1/responses", data=json.dumps(payload).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=cfg.get("timeout_s", 60)) as r:
            return json.loads(r.read())
    return call


def evidence_pack(ctx: dict, deal_id: str, question: str, as_of: str) -> list[dict]:
    """The passages the model may use: the deterministic answer's citations plus the top keyword hits."""
    base = qa.answer(ctx, deal_id, question, as_of)
    ids = list(dict.fromkeys(base["citations"] + [h["passage"] for h in search(ctx, deal_id, question, k=4, as_of=as_of)]))
    from .data import active_docs
    live = active_docs(ctx, as_of)
    pack = []
    for pid in ids:
        p = ctx["passages"][pid]
        d = ctx["docs"][p["doc"]]
        pack.append({"id": pid, "source": f"{d['author_role']}, {d['title']}, {d['date']}"
                     + ("" if p["doc"] in live else " (SUPERSEDED by a later version)"), "text": p["text"]})
    return pack


def _output_text(resp: dict) -> str:
    if resp.get("output_text"):
        return resp["output_text"]
    for item in resp.get("output", []):
        for c in item.get("content", []) or []:
            if c.get("type") == "output_text":
                return c["text"]
    raise ValueError("no text in model response")


def answer(ctx: dict, deal_id: str, question: str, as_of: str | None = None, *, client, budget: Budget) -> dict:
    as_of = as_of or latest_date(ctx)
    base = qa.answer(ctx, deal_id, question, as_of)
    res = {"question": question, "deal": deal_id, "as_of": as_of, "mode": "model", "claims": [], "rejected": [],
           "notes": [], "deterministic_status": base["status"]}
    if base.get("reason") in ("wrong_entity", "out_of_scope"):
        res["reason"] = base["reason"]
        res["notes"].append(f"{base['reason']}: declined before any model call")
        return _done(res, qa.INSUFFICIENT, base["answer"])
    pack = evidence_pack(ctx, deal_id, question, as_of)
    if not pack:
        return _done(res, qa.INSUFFICIENT, "No passages retrieved; no model call made.")
    cfg = budget.cfg
    user = json.dumps({"question": question, "passages": pack}, ensure_ascii=False)
    budget.reserve(len(INSTRUCTIONS) + len(user))
    payload = {"model": cfg["model"], "instructions": INSTRUCTIONS, "input": user,
               "max_output_tokens": cfg["max_output_tokens"], "reasoning": {"effort": cfg.get("reasoning_effort", "low")},
               "text": {"format": {"type": "json_schema", "name": "cited_answer", "schema": SCHEMA, "strict": True}}}
    try:
        resp = client(payload)
    except urllib.error.HTTPError as e:  # report the API's message, never the request (it carries the key)
        detail = e.read().decode("utf-8", "replace")[:300]
        raise ModelError(f"API returned HTTP {e.code}: {detail}") from None
    budget.record(resp.get("usage", {}))
    try:
        out = json.loads(_output_text(resp))
    except (ValueError, KeyError) as e:
        res["reason"] = "model_error"
        res["notes"].append(f"model output could not be read ({type(e).__name__}); answer withheld")
        return _done(res, qa.INSUFFICIENT, "Model output could not be read; answer withheld.")
    kept, rejected = qa.validate_citations(ctx, deal_id, as_of, out["claims"], allowed={p["id"] for p in pack})
    res["claims"] = [{**c, "role": "model"} for c in kept]
    res["rejected"] = rejected
    status = out["status"]
    if status != qa.INSUFFICIENT and not kept:
        res["notes"].append("every claim failed citation validation; answer withheld")
        status = qa.INSUFFICIENT
    if status == qa.INSUFFICIENT:
        res["reason"] = "no_evidence"
    if base["status"] == qa.CONFLICTED and status != qa.CONFLICTED:
        # the conflict check is deterministic; the model may word the answer but cannot flatten a conflict
        res["notes"].append(f"model answered {status} where live sources disagree; the conflict values from the "
                            "deterministic check were added and the outcome kept as CONFLICTED")
        have = {p for c in res["claims"] for p in c["passage_ids"]}
        res["claims"] += [{**c, "role": "conflict (deterministic)"} for c in base["claims"]
                          if c["role"] == "current" and not set(c["passage_ids"]) <= have]
        status = qa.CONFLICTED
    elif status != base["status"]:
        res["notes"].append(f"no-key mode says {base['status']}")
    return _done(res, status, " ".join(c["text"] for c in kept) or "Not answered from the evidence provided.")


def _done(res: dict, status: str, text: str) -> dict:
    res["status"], res["answer"] = status, text
    res["citations"] = sorted({p for c in res["claims"] for p in c["passage_ids"]})
    # values are not parsed from model text; the evaluation's value check uses the cited facts
    return res
