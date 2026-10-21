"""IC memo: from screening to an evidence-backed memo for human review, behind an approval gate.

The gate runs every check and lists every failure (it does not stop at the first):
  G1 citations      every claim cites at least one valid passage of this deal, dated on or before the memo date
  G2 currency       no claim cites a document version that a later version replaced
  G3 conflicts      a claim that depends on a conflicted fact needs a recorded conflict decision that allows memo use;
                    accepted conflicts stay visible in the memo ("accepted - sources still disagree")
  G4 red flags      every red flag for the deal has an owner and a due date
  G5 maker-checker  the reviewer is a different person from the drafter
  G6 evidence class a claim resting only on expert-call claims is labelled "unverified lead", not stated as fact
READY FOR IC REVIEW means the memo can go to the IC. The system never makes the investment decision: the IC's
decision is recorded by a person against the exact memo version (fingerprint), and only a READY memo can carry a
PROCEED decision.
"""
from __future__ import annotations

import hashlib
import json

from . import conflicts as cf
from . import graph as gr
from . import screening as sc
from .data import active_docs, fmt
from .qa import validate_citations

READY, BLOCKED = "READY FOR IC REVIEW", "BLOCKED"
IC_OPTIONS = ("PROCEED", "DECLINE", "REQUEST MORE WORK")


def _read(ctx: dict, name: str) -> list[dict]:
    p = ctx["data_dir"] / name
    return json.loads(p.read_text(encoding="utf-8"))["records"] if p.exists() else []


def load_memo(ctx: dict, deal_id: str) -> dict:
    return json.loads((ctx["data_dir"] / "memo" / f"{deal_id}.json").read_text(encoding="utf-8"))


def gate(ctx: dict, memo: dict) -> dict:
    deal, as_of = memo["deal"], memo["as_of"]
    company = ctx["deals"][deal]["company"]
    live = active_docs(ctx, as_of)
    checks: list[dict] = []

    def check(cid: str, name: str, failures: list[str]) -> None:
        checks.append({"id": cid, "name": name, "passed": not failures, "failures": failures})

    _, rejected = validate_citations(ctx, deal, as_of, memo["claims"])
    check("G1", "every claim cites a valid passage", [f"{c['id']}: {c['reason']}" for c in rejected])

    stale = [f"{c['id']}: cites {p}, replaced by a later version" for c in memo["claims"] for p in c["passage_ids"]
             if p in ctx["passages"] and ctx["passages"][p]["doc"] not in live and ctx["passages"][p]["date"] <= as_of]
    check("G2", "no citation to a replaced document version", stale)

    g = gr.build(ctx)
    fid_metric = {f["id"]: f["metric"] for f in ctx["facts"]}
    facts_by_passage: dict[str, list[str]] = {}
    for f in ctx["facts"]:
        facts_by_passage.setdefault(f["passage"], []).append(f["id"])
    for c in memo["claims"]:
        g.node(c["id"], "claim", text=c["text"])
        for p in c["passage_ids"]:
            g.edge(c["id"], "CITES", p)
            for fid in facts_by_passage.get(p, []):
                if not c.get("metrics") or fid_metric[fid] in c["metrics"]:
                    g.edge(c["id"], "DEPENDS_ON", fid)
    found = cf.detect(ctx, company, as_of)
    uses = gr.claims_on_conflicts(g, {x["id"]: [s["fact"] for s in x["sources"]] for x in found})
    decisions = {d["conflict"]: d for d in _read(ctx, "conflict_decisions.json")}
    bad, conflicts = [], []
    for x in found:
        d = decisions.get(x["id"])
        allowed = bool(d) and d["status"] in ("ACCEPTED", "RESOLVED") and d["memo_use"] == "ALLOWED_WITH_DISCLOSURE"
        for claim in uses[x["id"]]:
            if not d:
                bad.append(f"{claim}: depends on unresolved conflict {x['id']}")
            elif not allowed:
                bad.append(f"{claim}: conflict {x['id']} is recorded as not usable in the memo")
        conflicts.append({**x, "decision": d, "claims": uses[x["id"]]})
    check("G3", "claims on conflicted facts have a recorded decision", bad)

    flags = [r for r in _read(ctx, "red_flags.json") if r["deal"] == deal]
    check("G4", "every red flag has an owner and a due date",
          [f"{r['id']}: no {'owner' if not r['owner'] else 'due date'}" for r in flags if not (r["owner"] and r["due"])])

    mc = []
    if not memo.get("reviewed_by"):
        mc.append("no reviewer recorded")
    elif memo["reviewed_by"] == memo["drafted_by"]:
        mc.append(f"drafter and reviewer are the same ({memo['drafted_by']})")
    check("G5", "reviewer is not the drafter", mc)

    weak = []
    for c in memo["claims"]:
        classes = {ctx["passages"][p]["evidence_class"] for p in c["passage_ids"] if p in ctx["passages"]}
        if classes == {"expert-call claim"} and c.get("evidence_label") != "unverified lead":
            weak.append(f"{c['id']}: rests only on expert-call claims; label it an unverified lead")
    check("G6", "expert-call-only claims are labelled unverified", weak)

    status = READY if all(c["passed"] for c in checks) else BLOCKED
    return {"deal": deal, "as_of": as_of, "status": status, "checks": checks, "conflicts": conflicts,
            "red_flags": flags, "graph": g}


def render(ctx: dict, memo: dict, res: dict) -> str:
    """The memo body (everything except the IC decision). Its SHA-256 is the memo fingerprint."""
    d = ctx["deals"][memo["deal"]]
    s = sc.screen(ctx, memo["deal"], memo["as_of"])
    out = [f"# {d['name']} – IC memo v{memo['version']} ({memo['as_of']})", "",
           f"> {memo['label']} Prepared for discussion; the investment decision is the IC's.", "",
           f"Drafted by {memo['drafted_by']}; reviewed by {memo['reviewed_by']}. Evidence fingerprint {ctx['evidence_fingerprint'][:16]}.", "",
           f"## Gate: {res['status']}", ""]
    for c in res["checks"]:
        out.append(f"- {c['id']} {c['name']}: {'pass' if c['passed'] else 'FAIL'}")
        out += [f"    - {f}" for f in c["failures"]]
    out += ["", f"## Screening against {s['thesis']} (illustrative criteria)", ""]
    for r in s["rows"]:
        vals = ", ".join(f"{v['shown']} [{v['passage']}]" for v in r["evidence"]) or "no evidence"
        out.append(f"- {r['name']} {r['target']}: **{r['status']}** – {vals}")
    out.append(f"- Outcome: {s['outcome']}")
    sections: dict[str, list[dict]] = {}
    for c in memo["claims"]:
        sections.setdefault(c["section"], []).append(c)
    for sec, cs in sections.items():
        out += ["", f"## {sec}", ""]
        out += [f"- {'**Unverified lead:** ' if c.get('evidence_label') == 'unverified lead' else ''}{c['text']} "
                + (f"[{', '.join(c['passage_ids'])}]" if c["passage_ids"] else "**[no citation]**")
                + f" ({c['id']})" for c in cs]
    out += ["", "## Source conflicts", ""]
    for x in res["conflicts"]:
        vals = "; ".join(f"{fmt(ctx, x['metric'], v['value'])} [{v['passage']}]" for v in x["sources"])
        dd = x["decision"]
        state = (f"{dd['status'].lower()} – sources still disagree; base case {dd['base_case']}; {dd['accepted_by']}, "
                 f"{dd['at']}: \"{dd['rationale']}\"" if dd else "UNRESOLVED – no recorded decision")
        out.append(f"- {ctx['metrics'][x['metric']]['name']} ({x['period']}): {vals}. Status: {state}. "
                   f"Used by: {', '.join(x['claims']) or 'no claim'}")
    out += ["", "## Red flags", "", "| ID | Severity | Red flag | Treatment | Owner | Due | Action | Source |", "|---|---|---|---|---|---|---|---|"]
    for r in res["red_flags"]:
        out.append(f"| {r['id']} | {r['severity']} | {r['title']} | {r['treatment']} | {r['owner'] or '**none**'} | {r['due'] or '**none**'} | "
                   f"{r['action']} | {r['source']} |")
    return "\n".join(out) + "\n"


def memo_fingerprint(body: str) -> str:
    return hashlib.sha256(body.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def ic_decision(ctx: dict, deal_id: str, res: dict, fp: str) -> dict:
    """Read the human IC decision and check it against the gate and the exact memo version."""
    recs = [r for r in _read(ctx, "ic_decisions.json") if r["deal"] == deal_id]
    if not recs:
        return {"state": "NO DECISION RECORDED"}
    r = recs[-1]
    if r["decision"] not in IC_OPTIONS:
        return {"state": "INVALID", "record": r, "why": f"decision must be one of {', '.join(IC_OPTIONS)}"}
    if r["memo_fingerprint"] != fp:
        return {"state": "STALE", "record": r, "why": "recorded against an earlier memo version; the IC must re-confirm"}
    if r["decision"] == "PROCEED" and res["status"] != READY:
        return {"state": "INVALID", "record": r, "why": "PROCEED requires a memo that passed the gate"}
    return {"state": "RECORDED", "record": r}


def build(ctx: dict, deal_id: str) -> dict:
    memo = load_memo(ctx, deal_id)
    res = gate(ctx, memo)
    body = render(ctx, memo, res)
    fp = memo_fingerprint(body)
    dec = ic_decision(ctx, deal_id, res, fp)
    tail = ["", "## IC decision (human)", ""]
    if dec["state"] == "NO DECISION RECORDED":
        tail.append("No decision recorded. The system prepares the memo; it does not decide.")
    else:
        r = dec["record"]
        tail.append(f"**{r['decision']}** – {r['decided_by']}, {r['at']}. Rationale: \"{r['rationale']}\"")
        tail += [f"- Condition: {c}" for c in r.get("conditions", [])]
        tail.append(f"- Check: {dec['state']}" + (f" – {dec['why']}" if dec.get("why") else ""))
    tail.append(f"\nMemo fingerprint (SHA-256 of the body above the IC decision): {fp}")
    return {"memo": memo, "gate": res, "body": body, "fingerprint": fp, "decision": dec,
            "markdown": body + "\n".join(tail) + "\n"}
