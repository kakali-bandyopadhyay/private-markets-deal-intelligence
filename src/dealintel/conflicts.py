"""Source conflicts: two live sources that give different values for the same company, metric and period.

A superseded document version is not a conflict - the later version replaces it (see graph.changes).
Conflict IDs are stable across dates so decisions recorded against them keep pointing at the same thing.
"""
from __future__ import annotations

from .data import active_facts


def _differ(a, b, tol: float) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) > tol * max(abs(a), abs(b), 1e-9)
    return a != b


def detect(ctx: dict, company: str, as_of: str | None = None) -> list[dict]:
    tol = ctx["thesis"]["conflict_tolerance"]["relative"]
    groups: dict[tuple, list[dict]] = {}
    for f in active_facts(ctx, company, as_of):
        groups.setdefault((f["metric"], f["period"]), []).append(f)
    out = []
    for (metric, period), fs in sorted(groups.items()):
        values = [f["value"] for f in fs]
        if any(_differ(a, b, tol) for i, a in enumerate(values) for b in values[i + 1:]):
            out.append({"id": f"CF-{company[2:]}-{metric}-{period}", "company": company, "metric": metric,
                        "period": period,
                        "sources": [{"fact": f["id"], "passage": f["passage"], "value": f["value"],
                                     "basis": f["basis"], "date": f["date"]} for f in fs]})
    return out
