"""Diligence Q&A with citations (no-key mode, deterministic).

Every answer is a list of claims, each with the passage IDs behind it. Outcomes:
  SUPPORTED     one value (or one passage) answers it
  CONFLICTED    live sources disagree - all values are shown, none is picked
  CHANGED       a later document version replaced an earlier value - both are shown, the old one marked superseded
  INSUFFICIENT  not answered, with a reason:
                  no_evidence   nothing in the deal's live documents answers it
                  wrong_entity  the name or figure belongs to a similarly named, unrelated company
                  out_of_scope  the question is about another company that is not in the active deal
Answers use one active deal scope: documents about other companies exist in the corpus but are out of scope.

The system answers from the deal's documents only. It does not judge which source is right; that is a recorded
human decision (conflict register), and the investment decision is the IC's.
"""
from __future__ import annotations

import re

from .data import active_docs, active_facts, fmt, latest_date
from .search import search, tokens

SUPPORTED, CONFLICTED, CHANGED, INSUFFICIENT = "SUPPORTED", "CONFLICTED", "CHANGED", "INSUFFICIENT"
CHANGE_WORDS = re.compile(r"\b(chang(?!e[\s-]of[\s-]control)\w*|restat\w*|revis\w*|previous\w*|first issue|second issue|first (information )?memorandum|"
                          r"second (information )?memorandum|earlier version|new version)\b")
NUM = re.compile(r"(?:usd|eur|\$|€)?\s?(\d+(?:\.\d+)?)\s?(%|m\b|bn\b)")
MIN_MATCHED, MIN_COVERAGE = 2, 0.5


def _find(text: str, phrases: dict[str, str]) -> list[tuple[str, str]]:
    """Longest-first phrase match on word boundaries; returns (key, phrase), most specific (longest) phrase first."""
    found, taken = [], []
    for ph in sorted(phrases, key=len, reverse=True):
        for m in re.finditer(rf"\b{re.escape(ph)}\b", text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append((phrases[ph], ph))
    return found


def _value_claims(ctx: dict, metric: str, facts: list[dict], role: str) -> list[dict]:
    tol = ctx["thesis"]["conflict_tolerance"]["relative"]
    groups: list[list[dict]] = []
    for f in sorted(facts, key=lambda f: (f["date"], f["passage"])):
        for g in groups:
            v = g[0]["value"]
            same = (abs(v - f["value"]) <= tol * max(abs(v), abs(f["value"]), 1e-9)
                    if isinstance(v, (int, float)) else v == f["value"])
            if same:
                g.append(f)
                break
        else:
            groups.append([f])
    out = []
    for g in groups:
        f0 = g[0]
        srcs = "; ".join(f"{ctx['docs'][f['doc']]['author_role']}, {ctx['docs'][f['doc']]['title']}" for f in g)
        basis = "; ".join(sorted({f["basis"] for f in g if f["basis"]}))
        out.append({"text": f"{ctx['metrics'][metric]['name']} ({f0['period']}): {fmt(ctx, metric, f0['value'])} – {srcs}"
                            + (f" [{basis}]" if basis else ""),
                    "value": f0["value"], "passage_ids": [f["passage"] for f in g], "role": role})
    return out


def answer(ctx: dict, deal_id: str, question: str, as_of: str | None = None) -> dict:
    as_of = as_of or latest_date(ctx)
    deal = ctx["deals"][deal_id]
    company = deal["company"]
    q = question.lower()
    res = {"question": question, "deal": deal_id, "as_of": as_of, "metric": None, "claims": [], "notes": []}

    names = {a: c["id"] for c in ctx["companies"].values() for a in c["aliases"]}
    others = [c for c, _ in _find(q, names) if c != company]
    generic = {"project", "inc", "ltd", "group"}
    target_words = set(" ".join(ctx["companies"][company]["aliases"]).split()) - generic
    if others:
        o = ctx["companies"][others[0]]
        if target_words & set(" ".join(o["aliases"]).split()):
            res["reason"] = "wrong_entity"
            return _done(res, INSUFFICIENT, f"The question is about {o['code_name']}, a different company with a similar "
                                            f"name to {deal['name']}. Not answered from this deal's evidence.")
        res["reason"] = "out_of_scope"
        return _done(res, INSUFFICIENT, f"The question is about {o['code_name']}, which is not in the active deal "
                                        f"scope ({deal['name']}). Not answered from this deal's evidence.")

    # a figure quoted in the question that no target passage contains, but another company's passage does
    in_scope = [p for p in ctx["passages"].values() if p["deal"] == deal_id and p["date"] <= as_of]
    for num, unit in NUM.findall(q):
        tok = (num, unit)
        if any(tok in NUM.findall(p["text"].lower()) for p in in_scope):
            continue
        elsewhere = [p for p in ctx["passages"].values() if p["company"] not in (company, None)
                     and tok in NUM.findall(p["text"].lower())]
        if elsewhere:
            o = ctx["companies"][elsewhere[0]["company"]]
            res["reason"] = "wrong_entity"
            res["notes"].append(f"{num}{unit} appears only in {elsewhere[0]['doc']}, about {o['code_name']}")
            return _done(res, INSUFFICIENT, f"No source for {deal['name']} gives {num}{unit}; that figure belongs to "
                                            f"{o['code_name']}, a different company. Not answered from this deal's evidence.")

    period = None
    m = re.search(r"\bfy\s?(20\d\d)\b", q)
    if m:
        period = f"FY{m.group(1)}"
    aliases = {a: k for k, v in ctx["metrics"].items() for a in v["aliases"]}
    found = _find(q, aliases)
    change = bool(CHANGE_WORDS.search(q))

    text_hit = None
    if found:
        # a question with real content beyond the metric phrase ("does the largest customer's contract contain a
        # change-of-control clause?") is a text question, not a request for the figure
        ignore = set(tokens(" ".join(ctx["companies"][company]["aliases"]) + " " + found[0][1]))
        hits = search(ctx, deal_id, question, k=1, as_of=as_of, ignore=ignore)
        if hits and len(hits[0]["matched"]) >= 3:
            text_hit = hits[0]
    if found and not text_hit:
        metric = found[0][0]
        res["metric"] = metric
        live = [f for f in active_facts(ctx, company, as_of) if f["metric"] == metric and (not period or f["period"] == period)]
        live_docs = active_docs(ctx, as_of)
        old = [f for f in ctx["facts"] if f["company"] == company and f["metric"] == metric
               and f["date"] <= as_of and f["doc"] not in live_docs and (not period or f["period"] == period)]
        if not live:
            res["reason"] = "no_evidence"
            return _done(res, INSUFFICIENT, f"No sourced figure for {ctx['metrics'][metric]['name'].lower()}"
                                            + (f" for {period}" if period else "") + " in this deal's live documents.")
        cur = _value_claims(ctx, metric, live, "current")
        if change:
            old_vals = {round(f["value"], 6) if isinstance(f["value"], float) else f["value"] for f in old}
            new_vals = {round(c["value"], 6) if isinstance(c["value"], float) else c["value"] for c in cur}
            if old and old_vals != new_vals:
                prev = _value_claims(ctx, metric, old, "superseded")
                for c in prev:
                    repl = sorted({d["key"] for d in ctx["docs"].values()
                                   if d["supersedes"] in {ctx["passages"][p]["doc"] for p in c["passage_ids"]}})
                    c["text"] += f" – superseded by {', '.join(repl)}"
                new_docs = {d["key"] for d in ctx["docs"].values() if d["supersedes"] in {f["doc"] for f in old}}
                for c in cur:
                    if not {ctx["passages"][p]["doc"] for p in c["passage_ids"]} & new_docs:
                        c["role"] = "other source"
                cur.sort(key=lambda c: c["role"] != "current")
                res["claims"] = cur + prev + _explanations(ctx, deal_id, question, as_of, old)
                if len(cur) > 1:
                    res["notes"].append("separately, live sources disagree on the current value (a source conflict, "
                                        "not a version change; see the conflict register)")
                return _done(res, CHANGED, "The figure changed between document versions. " + _summary(cur, prev))
            res["notes"].append("no version change recorded for this figure")
        res["claims"] = cur
        if len(cur) > 1:
            return _done(res, CONFLICTED, "Sources disagree; no value is picked. " + _summary(cur))
        return _done(res, SUPPORTED, cur[0]["text"])

    ignore = set(tokens(" ".join(ctx["companies"][company]["aliases"])))
    hits = search(ctx, deal_id, question, k=3, as_of=as_of, ignore=ignore)
    good = [h for h in hits if len(h["matched"]) >= MIN_MATCHED and len(h["matched"]) / max(len(h["query_terms"]), 1) >= MIN_COVERAGE]
    if not good:
        if hits:
            res["notes"].append(f"closest passage {hits[0]['passage']} matched only {hits[0]['matched']}; not cited")
        res["reason"] = "no_evidence"
        return _done(res, INSUFFICIENT, "No passage in this deal's live documents answers this.")
    top = good[0]
    cls = ctx["passages"][top["passage"]]["evidence_class"]
    res["claims"] = [{"text": ctx["passages"][top["passage"]]["text"], "passage_ids": [top["passage"]], "role": "quote",
                      "evidence_class": cls}]
    res["notes"].append(f"evidence class: {cls}" + (" – a lead to verify, not an established fact" if cls == "expert-call claim" else ""))
    return _done(res, SUPPORTED, ctx["passages"][top["passage"]]["text"])


def _explanations(ctx: dict, deal_id: str, question: str, as_of: str, old: list[dict]) -> list[dict]:
    """The passage in the replacing version that explains the change, if search finds one."""
    old_docs = {f["doc"] for f in old}
    new_docs = {d["key"] for d in ctx["docs"].values() if d["supersedes"] in old_docs}
    hits = [h for h in search(ctx, deal_id, question + " restated replaces exclude", k=10, as_of=as_of)
            if ctx["passages"][h["passage"]]["doc"] in new_docs]
    fact_ps = {f["passage"] for f in ctx["facts"]}
    for h in hits:
        if h["passage"] not in fact_ps:
            return [{"text": ctx["passages"][h["passage"]]["text"], "passage_ids": [h["passage"]], "role": "explanation"}]
    return []


def _summary(*groups: list[dict]) -> str:
    return " | ".join(c["text"] for g in groups for c in g)


def _done(res: dict, status: str, text: str) -> dict:
    res["status"] = status
    res["answer"] = text
    res["citations"] = sorted({p for c in res["claims"] for p in c["passage_ids"]})
    return res


def validate_citations(ctx: dict, deal_id: str, as_of: str, claims: list[dict],
                       allowed: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    """Citation validation (not fact verification): keep claims whose passage IDs all exist, belong to the deal, are
    dated on or before as_of and - when `allowed` is given - were among the retrieved passages. Whether a passage
    actually supports the claim is assessed separately, in the evaluation."""
    kept, rejected = [], []
    for c in claims:
        ids = c.get("passage_ids") or []
        bad = [p for p in ids if p not in ctx["passages"] or ctx["passages"][p]["deal"] != deal_id
               or ctx["passages"][p]["date"] > as_of or (allowed is not None and p not in allowed)]
        if not ids or bad:
            rejected.append({**c, "reason": "no passage ID" if not ids else f"invalid passage ID(s): {', '.join(bad)}"})
        else:
            kept.append(c)
    return kept, rejected


def as_text(r: dict) -> str:
    out = [f"Q [{r['deal']}, as of {r['as_of']}]: {r['question']}", f"  {r['status']}: {r['answer']}"]
    for c in r["claims"]:
        out.append(f"   - ({c['role']}) {c['text']}  [{', '.join(c['passage_ids'])}]")
    out += [f"  note: {n}" for n in r["notes"]]
    return "\n".join(out)
