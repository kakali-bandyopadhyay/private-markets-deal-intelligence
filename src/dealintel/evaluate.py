"""Prototype evaluation on a small, hand-authored question set (data/eval/questions.json).

Measures are reported separately and per question:
  status            the outcome matches the hand-labelled one (SUPPORTED / CONFLICTED / CHANGED / INSUFFICIENT)
  citation valid    every cited passage exists, belongs to the deal and is dated on or before the as-of date
                    (automatic; says nothing about whether the passage supports the answer)
  citation support  the cited passages include every hand-labelled expected passage and nothing outside the
                    hand-labelled supporting set (a proxy for "the passage supports the claim", only as good as
                    the labels; a column is left for a person's spot check)
  values            every expected value appears in the answer's claims
  refusal           questions labelled INSUFFICIENT are declined; others are not
  conflict          questions labelled CONFLICTED show the disagreement; others do not invent one

This is a prototype evaluation, not investment-grade validation.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import qa
from .data import DATA, latest_date


def load_questions(path: Path | None = None) -> list[dict]:
    return json.loads((path or DATA / "eval" / "questions.json").read_text(encoding="utf-8"))["questions"]


def _shown(v) -> list[str]:
    if isinstance(v, str):
        return [v]
    out = [f"{v:g}"]
    if 0 < v < 2:
        out.append(f"{v * 100:g}%")
    return out


def _has_value(claims: list[dict], v) -> bool:
    for c in claims:
        if "value" not in c and any(s in c.get("text", "") for s in _shown(v)):
            return True
        cv = c.get("value")
        if isinstance(v, float) and isinstance(cv, (int, float)) and abs(cv - v) < 1e-9:
            return True
        if cv == v:
            return True
    return False


def score(ctx: dict, q: dict, r: dict) -> dict:
    as_of = q.get("as_of") or latest_date(ctx)
    cites = r["citations"]
    _, rejected = qa.validate_citations(ctx, q["deal"], as_of, [{"passage_ids": [p]} for p in cites])
    valid = not rejected
    exp, ok_set = set(q["expected_passages"]), set(q["expected_passages"]) | set(q["acceptable_passages"])
    support = (exp <= set(cites) and set(cites) <= ok_set) if q["expected_status"] != "INSUFFICIENT" else not cites
    values = all(_has_value(r["claims"], v) for v in q.get("expected_values", []))
    return {"id": q["id"], "category": q["category"], "deal": q["deal"], "question": q["question"],
            "expected": q["expected_status"], "got": r["status"], "status_ok": r["status"] == q["expected_status"],
            "citations": cites, "citation_valid": valid, "citation_support": support, "values_ok": values,
            "human_check": ""}


def run(ctx: dict, questions: list[dict] | None = None, answer_fn=None) -> dict:
    answer_fn = answer_fn or (lambda q: qa.answer(ctx, q["deal"], q["question"], q.get("as_of")))
    rows = [score(ctx, q, answer_fn(q)) for q in (questions or load_questions())]
    n = len(rows)
    refuse_exp = [r for r in rows if r["expected"] == "INSUFFICIENT"]
    answer_exp = [r for r in rows if r["expected"] != "INSUFFICIENT"]
    conf_exp = [r for r in rows if r["expected"] == "CONFLICTED"]
    other = [r for r in rows if r["expected"] != "CONFLICTED"]
    all_cites = sum(len(r["citations"]) for r in rows)
    summary = {
        "questions": n,
        "status_accuracy": f"{sum(r['status_ok'] for r in rows)}/{n}",
        "citation_validity": f"{sum(len(r['citations']) for r in rows if r['citation_valid'])}/{all_cites} citations",
        "citation_support": f"{sum(r['citation_support'] for r in answer_exp)}/{len(answer_exp)} answered questions",
        "expected_values_present": f"{sum(r['values_ok'] for r in answer_exp)}/{len(answer_exp)}",
        "appropriate_refusal": f"{sum(r['got'] == 'INSUFFICIENT' for r in refuse_exp)}/{len(refuse_exp)} declined when they should",
        "false_refusal": f"{sum(r['got'] == 'INSUFFICIENT' for r in answer_exp)}/{len(answer_exp)} declined when they should not",
        "conflict_detection": f"{sum(r['got'] == 'CONFLICTED' for r in conf_exp)}/{len(conf_exp)} conflicts shown",
        "false_conflicts": f"{sum(r['got'] == 'CONFLICTED' for r in other)}/{len(other)}",
        "by_category": {c: f"{sum(r['status_ok'] and r['citation_support'] for r in rows if r['category'] == c)}/"
                           f"{sum(r['category'] == c for r in rows)}" for c in dict.fromkeys(r["category"] for r in rows)},
        "label": "Small, hand-authored prototype set; the rules were developed alongside it, so results are optimistic. "
                 "Not investment-grade validation.",
    }
    return {"summary": summary, "rows": rows}


def as_markdown(res: dict, mode: str = "no-key") -> str:
    s = res["summary"]
    out = [f"# Prototype evaluation ({mode} mode)", "", f"> {s['label']}", "",
           "| Measure | Result |", "|---|---|"]
    for k in ("status_accuracy", "citation_validity", "citation_support", "expected_values_present",
              "appropriate_refusal", "false_refusal", "conflict_detection", "false_conflicts"):
        out.append(f"| {k.replace('_', ' ')} | {s[k]} |")
    out += ["", "By category (status and citation support both correct): "
            + ", ".join(f"{k} {v}" for k, v in s["by_category"].items()), "",
            "| ID | Category | Question | Expected | Got | Citation valid | Citation support | Values | Human check |",
            "|---|---|---|---|---|---|---|---|---|"]
    yn = lambda b: "yes" if b else "**no**"
    for r in res["rows"]:
        out.append(f"| {r['id']} | {r['category']} | {r['question']} | {r['expected']} | {r['got']} | "
                   f"{yn(r['citation_valid'])} | {yn(r['citation_support'])} | {yn(r['values_ok'])} | {r['human_check']} |")
    return "\n".join(out) + "\n"
