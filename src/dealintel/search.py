"""Keyword search (BM25) over passages, restricted to one deal's live documents.

This is plain search, not a graph feature. Scope is applied before ranking: only passages from documents in the
deal (and live on the as-of date) can be returned, so a similarly named company elsewhere in the corpus never enters.
"""
from __future__ import annotations

import math
import re

from .data import active_docs

STOP = set("""a an and are as at be by did do does for from has have how in is it its of on or our the their this to was
were what when where which who why will with than that these those there any we us vs versus say said says about into
after before over under per also more most much many current currently company business project
main here now look like would should could get make""".split())


# Small domain synonym list for query terms (a stopgap for paraphrases; embeddings are the tested alternative - see
# docs/TRADEOFFS.md T2). Each query term matches a passage if the term or any listed alternative appears.
SYNONYMS = {
    "growing": ["growth", "grow"], "grow": ["growth", "growing"], "growth": ["grow", "growing"],
    "lever": ["plan", "driver"], "driver": ["plan", "lever"],
    "sticky": ["switching", "churn", "retention"], "stickiness": ["switching", "churn", "retention"],
    "risk": ["red", "flag"], "issue": ["finding"],
}


def tokens(text: str) -> list[str]:
    out = []
    for t in re.findall(r"[a-z0-9]+", text.lower()):
        if t in STOP or len(t) < 2:
            continue
        if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


def scope(ctx: dict, deal_id: str, as_of: str | None = None, include_superseded: bool = False) -> list[dict]:
    live = active_docs(ctx, as_of)
    keep = []
    for p in ctx["passages"].values():
        if p["deal"] != deal_id:
            continue
        if p["doc"] in live or (include_superseded and (as_of is None or p["date"] <= as_of)):
            keep.append(p)
    return keep


def search(ctx: dict, deal_id: str, query: str, k: int = 5, as_of: str | None = None,
           ignore: set[str] = frozenset(), k1: float = 1.2, b: float = 0.75) -> list[dict]:
    ps = scope(ctx, deal_id, as_of)
    docs = [tokens(p["text"]) for p in ps]
    if not docs:
        return []
    avg = sum(map(len, docs)) / len(docs)
    q = [t for t in dict.fromkeys(tokens(query)) if t not in ignore]
    alts = {t: [t] + SYNONYMS.get(t, []) for t in q}
    n = len(docs)
    df = {t: sum(any(a in d for a in alts[t]) for d in docs) for t in q}
    weights = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in q}
    hits = []
    for p, d in zip(ps, docs):
        s, matched = 0.0, []
        for t in q:
            tf = sum(d.count(a) for a in alts[t])
            if not tf:
                continue
            matched.append(t)
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d) / avg))
        if s > 0:
            hits.append({"passage": p["id"], "score": round(s, 3), "matched": matched, "query_terms": q,
                         "weights": weights})
    hits.sort(key=lambda h: (-h["score"], h["passage"]))
    return hits[:k]
