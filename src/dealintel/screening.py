"""Thesis screening: each criterion is MET, NOT MET, UNKNOWN or CONFLICTED, with the evidence behind it.

Screening criteria, not a recommendation. The criteria are versioned, illustrative data (data/thesis.json);
a person on the deal team records the screening decision (data/screening_decisions.json).
"""
from __future__ import annotations

from .data import active_facts, fmt, latest_date

MET, NOT_MET, UNKNOWN, CONFLICTED = "MET", "NOT MET", "UNKNOWN", "CONFLICTED"


def _passes(op: str, target, value) -> bool:
    if op == ">=":
        return value >= target
    if op == "<=":
        return value <= target
    if op == "between":
        return target[0] <= value <= target[1]
    if op == "in":
        return value in target
    raise ValueError(f"unknown operator {op}")


def _target(ctx: dict, c: dict) -> str:
    m, v = c["metric"], c["value"]
    if c["op"] == "between":
        return f"between {fmt(ctx, m, v[0])} and {fmt(ctx, m, v[1])}"
    if c["op"] == "in":
        return "is a European country"
    return f"{c['op']} {fmt(ctx, m, v)}"


def screen(ctx: dict, deal_id: str, as_of: str | None = None) -> dict:
    deal = ctx["deals"][deal_id]
    th = ctx["thesis"]
    if deal["thesis"] != th["key"]:
        raise ValueError(f"{deal_id} is screened against {deal['thesis']}, loaded thesis is {th['key']}")
    as_of = as_of or latest_date(ctx)
    tol = th["conflict_tolerance"]["relative"]
    facts = active_facts(ctx, deal["company"], as_of)
    rows = []
    for c in th["criteria"]:
        ev = [f for f in facts if f["metric"] == c["metric"]]
        vals = [{"value": f["value"], "shown": fmt(ctx, f["metric"], f["value"]), "passage": f["passage"],
                 "basis": f["basis"], "passes": _passes(c["op"], c["value"], f["value"])} for f in ev]
        distinct = []
        for v in vals:
            if not any((abs(v["value"] - d) <= tol * max(abs(v["value"]), abs(d), 1e-9))
                       if isinstance(d, (int, float)) and isinstance(v["value"], (int, float)) else v["value"] == d
                       for d in distinct):
                distinct.append(v["value"])
        if not vals:
            status, note = UNKNOWN, "no evidence in the live documents"
        elif len(distinct) > 1:
            status = CONFLICTED
            note = ("sources disagree; every source value passes" if all(v["passes"] for v in vals)
                    else "sources disagree; outcome depends on which source holds")
        else:
            status = MET if vals[0]["passes"] else NOT_MET
            note = f"{len(vals)} source(s) agree"
        open_q = status == UNKNOWN or (status == CONFLICTED and not all(v["passes"] for v in vals))
        rows.append({"criterion": c["id"], "metric": c["metric"], "name": ctx["metrics"][c["metric"]]["name"],
                     "target": _target(ctx, c), "why": c["why"], "status": status, "note": note,
                     "open_question": open_q, "evidence": vals})
    n_not = sum(r["status"] == NOT_MET for r in rows)
    n_open = sum(r["open_question"] for r in rows)
    mx = th["screening_rule"]["max_open"]
    if n_not:
        outcome = f"DOES NOT MEET THE CRITERIA ({n_not} not met)"
    elif n_open > mx:
        outcome = f"NOT ENOUGH EVIDENCE TO SCREEN ({n_open} open, limit {mx})"
    else:
        outcome = f"MEETS THE SCREENING CRITERIA – {n_open} open question(s) for diligence"
    return {"deal": deal_id, "name": deal["name"], "thesis": th["key"], "as_of": as_of, "rows": rows,
            "outcome": outcome, "conflicted_policy": th["screening_rule"]["conflicted_policy"], "open": n_open, "not_met": n_not, "label": th["label"],
            "decision": next((d for d in ctx["screening_decisions"]
                              if d["deal"] == deal_id and d["as_of"] <= as_of), None)}


def as_text(r: dict) -> str:
    out = [f"Screening {r['deal']} {r['name']} against {r['thesis']} as of {r['as_of']}",
           f"  ({r['label']})"]
    for x in r["rows"]:
        out.append(f"  {x['criterion']:<7} {x['status']:<10} {x['name']} {x['target']}"
                   + ("   <- open question for diligence" if x["open_question"] else ""))
        out.append(f"          {x['note']}")
        for v in x["evidence"]:
            out.append(f"          {v['shown']:<10} {'pass' if v['passes'] else 'FAIL'}  {v['passage']}"
                       + (f"  [{v['basis']}]" if v["basis"] else ""))
    out.append(f"  Outcome: {r['outcome']}")
    out.append(f"  Conflicted criteria: {r['conflicted_policy']}")
    d = r["decision"]
    out.append(f"  Human decision: {d['decision']} by {d['decided_by']} on {d['at']} - \"{d['rationale']}\""
               if d else "  Human decision: not yet recorded")
    return "\n".join(out)
