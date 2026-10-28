"""Static dashboard (docs/index.html): the pipeline, one deal's journey from screening to the human IC decision,
and the evaluation and value evidence. Built from the same functions as the CLI, so it cannot disagree with them."""
from __future__ import annotations

from html import escape as e

from . import conflicts as cf
from . import evaluate as ev
from . import memo as mm
from . import qa
from . import screening as sc
from . import value
from .data import fmt, latest_date

CSS = """
:root{--bg:#f7f8fa;--card:#fff;--ink:#1d2433;--mute:#5b6475;--line:#e3e6ec;--accent:#1f4e8c;
--ok:#1e7a46;--okbg:#e7f4ec;--warn:#9a5b00;--warnbg:#fff3df;--bad:#a12a2a;--badbg:#fbe9e9;--info:#3b4a6b;--infobg:#eef1f7}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1a1f27;--ink:#e6e9ef;--mute:#9aa3b2;--line:#2b3240;
--accent:#8fb4ea;--ok:#7fd3a0;--okbg:#17301f;--warn:#f0c070;--warnbg:#33280f;--bad:#f09a9a;--badbg:#3a1a1a;--info:#b8c4dd;--infobg:#232a38}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 12px}
h3{font-size:15px;margin:0 0 8px}.sub{color:var(--mute);margin:0 0 16px}.banner{background:var(--infobg);color:var(--info);
border-radius:8px;padding:10px 14px;font-size:13px}.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}.mute{color:var(--mute);font-size:13px}
.pill{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:600}
.ok{background:var(--okbg);color:var(--ok)}.warn{background:var(--warnbg);color:var(--warn)}.bad{background:var(--badbg);color:var(--bad)}
.info{background:var(--infobg);color:var(--info)}table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--mute);font-weight:600}
.wrap{overflow-x:auto}.steps{counter-reset:s;list-style:none;padding:0;margin:0}.steps>li{position:relative;padding:0 0 18px 40px;border-left:2px solid var(--line);margin-left:14px}
.steps>li:last-child{border-left-color:transparent}.steps>li:before{counter-increment:s;content:counter(s);position:absolute;left:-15px;top:-2px;width:28px;height:28px;
border-radius:50%;background:var(--accent);color:var(--card);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}
.human:before{background:var(--ok)!important}code{font-size:12px;background:var(--infobg);padding:1px 4px;border-radius:4px}
details{margin-top:6px}summary{cursor:pointer;color:var(--accent);font-size:13px}.big{font-size:22px;font-weight:700}
"""
STATUS = {"MET": "ok", "NOT MET": "bad", "UNKNOWN": "warn", "CONFLICTED": "warn", "SUPPORTED": "ok", "CONFLICTED ": "warn",
          "CHANGED": "info", "INSUFFICIENT": "warn", "READY FOR IC REVIEW": "ok", "BLOCKED": "bad"}


def pill(text: str, kind: str | None = None) -> str:
    return f'<span class="pill {kind or STATUS.get(text, "info")}">{e(text)}</span>'


def _screen_table(r: dict) -> str:
    rows = "".join(
        f"<tr><td>{e(x['name'])}<div class='mute'>{e(x['target'])}</div></td><td>{pill(x['status'])}"
        + (" <span class='mute'>open question</span>" if x["open_question"] else "") + "</td><td>"
        + ("<br>".join(f"{e(v['shown'])} {'pass' if v['passes'] else '<b>fail</b>'} <code>{e(v['passage'])}</code>"
                       for v in x["evidence"]) or "<span class='mute'>no evidence</span>") + "</td></tr>"
        for x in r["rows"])
    return (f"<div class='wrap'><table><tr><th>Criterion</th><th>Status</th><th>Evidence</th></tr>{rows}</table></div>"
            f"<p class='mute'>Outcome: {e(r['outcome'])}</p>")


def build(ctx: dict) -> str:
    lark = mm.build(ctx, "D-LARK")
    osier = mm.build(ctx, "D-OSIER")
    s0 = sc.screen(ctx, "D-LARK", "2026-05-12")
    s1 = sc.screen(ctx, "D-LARK", lark["memo"]["as_of"])
    evr = ev.run(ctx)
    val = value.estimate()
    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="/assets/favicon-32x32.png" sizes="32x32"><link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<title>Deal Intelligence Prototype</title><style>{CSS}</style></head><body><main>
<h1>Private-markets deal intelligence</h1><p class="sub">From screening to an evidence-backed IC memo for human review – personal prototype</p>
<div class="banner">Synthetic companies, documents and figures. Illustrative screening criteria and policies. Not connected to, or based on, any firm's systems or processes. The system prepares evidence; people make every decision.</div>
<h2>Pipeline</h2><div class="grid">"""]
    for deal_id, m in (("D-LARK", lark), ("D-OSIER", osier), ("D-BRAM", None)):
        d = ctx["deals"][deal_id]
        s = sc.screen(ctx, deal_id)
        dec = s["decision"]
        gate = pill(m["gate"]["status"]) if m else "<span class='mute'>no memo</span>"
        icd = m["decision"] if m else {"state": "NO DECISION RECORDED"}
        ic = (pill(icd["record"]["decision"], "ok") + f" <span class='mute'>{e(icd['record']['decided_by'])}</span>"
              if icd.get("record") and icd["state"] == "RECORDED" else "<span class='mute'>none recorded</span>")
        parts.append(f"<div class='card'><h3>{e(d['name'])}</h3><div class='mute'>{e(ctx['companies'][d['company']]['subsector'])} · "
                     f"{e(d['role'])}</div><p>Screening: {e(s['outcome'])}<br>Screening decision: "
                     f"{e(dec['decision']) if dec else '<span class=mute>none</span>'}<br>Memo gate: {gate}<br>IC decision: {ic}</p></div>")
    parts.append("</div>")

    g = lark["gate"]
    conflicts = g["conflicts"]
    parts.append("<h2>One deal, end to end: Project Larkspur</h2><ol class='steps'>")
    parts.append(f"<li><h3>Screening on the first memorandum (12 May)</h3>{_screen_table(s0)}"
                 f"<p class='mute'>Recorded by a person: {e(s0['decision']['decision'])} – \"{e(s0['decision']['rationale'])}\"</p></li>")
    ch = qa.answer(ctx, "D-LARK", "How did revenue change between the first and second information memorandum?")
    parts.append("<li><h3>Evidence changes: restated memorandum and adviser reports</h3>"
                 + "".join(f"<div>{e(c['text'])} <code>{e(', '.join(c['passage_ids']))}</code></div>" for c in ch["claims"])
                 + f"<details><summary>Screening as of {e(s1['as_of'])}</summary>{_screen_table(s1)}</details></li>")
    rows = "".join(
        f"<tr><td>{e(ctx['metrics'][x['metric']]['name'])}</td><td>"
        + "<br>".join(f"{e(fmt(ctx, x['metric'], v['value']))} <code>{e(v['passage'])}</code>" for v in x["sources"])
        + f"</td><td>{pill('accepted – sources still disagree', 'warn') if x['decision'] else pill('unresolved', 'bad')}"
        + (f"<div class='mute'>{e(x['decision']['accepted_by'])}: {e(x['decision']['rationale'])}</div>" if x["decision"] else "")
        + f"</td><td>{e(', '.join(x['claims']) or '–')}</td></tr>" for x in conflicts)
    parts.append(f"<li><h3>Source conflicts: shown, decided by a person, kept visible</h3><div class='wrap'><table><tr><th>Figure</th>"
                 f"<th>Sources</th><th>Decision</th><th>Memo claims</th></tr>{rows}</table></div></li>")
    flags = "".join(f"<tr><td>{e(r['id'])}</td><td>{pill(r['severity'], 'bad' if r['severity'] == 'High' else 'warn')}</td>"
                    f"<td>{e(r['title'])}</td><td>{e(r['treatment'])}</td><td>{e(r['owner'] or 'none')}</td><td>{e(r['due'] or 'none')}</td></tr>" for r in g["red_flags"])
    checks = "".join(f"<tr><td>{e(c['id'])}</td><td>{e(c['name'])}</td><td>{pill('pass', 'ok') if c['passed'] else pill('fail', 'bad')}</td></tr>"
                     for c in g["checks"])
    parts.append(f"<li><h3>IC memo gate: {pill(g['status'])}</h3><div class='grid'><div class='wrap'><table>{checks}</table></div>"
                 f"<div class='wrap'><table><tr><th>ID</th><th>Severity</th><th>Red flag</th><th>Treatment</th><th>Owner</th><th>Due</th></tr>{flags}</table></div></div>"
                 f"<details><summary>Memo claims ({len(lark['memo']['claims'])}, each cited)</summary>"
                 + "".join(f"<div>{e(c['text'])} <code>{e(', '.join(c['passage_ids']))}</code></div>" for c in lark["memo"]["claims"])
                 + "</details></li>")
    r = lark["decision"]["record"]
    parts.append(f"<li class='human'><h3>Human IC decision: {pill(r['decision'], 'ok')}</h3><p>{e(r['decided_by'])}, {e(r['at'])}. "
                 f"\"{e(r['rationale'])}\"</p><ul>" + "".join(f"<li>{e(c)}</li>" for c in r.get("conditions", []))
                 + f"</ul><p class='mute'>Recorded against memo fingerprint <code>{e(lark['fingerprint'][:16])}</code>; check: {e(lark['decision']['state'])}. "
                 "If the memo changes, the decision shows as stale until the IC re-confirms.</p></li></ol>")

    of = "".join(f"<li>{e(c['id'])}: {e('; '.join(c['failures']))}</li>" for c in osier["gate"]["checks"] if not c["passed"])
    parts.append(f"<h2>Contrast: Project Osier is blocked at the gate</h2><div class='card'><ul>{of}</ul></div>")

    sm = evr["summary"]
    m_rows = "".join(f"<tr><td>{e(k.replace('_', ' '))}</td><td>{e(sm[k])}</td></tr>" for k in
                     ("status_accuracy", "citation_validity", "citation_support", "appropriate_refusal", "false_refusal",
                      "conflict_detection", "false_conflicts"))
    q_rows = "".join(f"<tr><td>{e(x['id'])}</td><td>{e(x['question'])}</td><td>{pill(x['got'])}</td><td>"
                     f"{'yes' if x['citation_support'] else '<b>no</b>'}</td></tr>" for x in evr["rows"])
    import json as _json
    log = _json.loads((ctx["data_dir"] / "eval" / "run_log.json").read_text(encoding="utf-8"))
    lr = "".join(f"<tr><td>{e(r['run'])}</td><td>{pill(r['kind'], 'ok' if r['kind'] == 'held-out' else 'info')}</td>"
                 f"<td>{r['questions']}</td><td>{e(r['authorship'])}</td><td>{e(r['mode'])}</td><td><code>{e(r['code'])}</code></td>"
                 f"<td><b>{e(r['correct'])}</b></td><td>{e(r['citations'])}</td></tr>" for r in log["runs"])
    parts.append(f"<h2>Evaluation runs</h2><p class='mute'>{e(log['note'])} Misses and causes: docs/FINDINGS.md.</p>"
                 f"<div class='card'><div class='wrap'><table><tr><th>Run</th><th>Kind</th><th>Questions</th><th>Authorship</th>"
                 f"<th>Mode</th><th>Code</th><th>Correct outcome</th><th>Citations</th></tr>{lr}</table></div></div>")
    parts.append(f"<h2>Development set detail (no-key mode)</h2><p class='mute'>{e(sm['label'])}</p><div class='grid'>"
                 f"<div class='card'><div class='wrap'><table>{m_rows}</table></div></div><div class='card'><div class='mute'>"
                 f"By category: {e(', '.join(f'{k} {v}' for k, v in sm['by_category'].items()))}</div>"
                 f"<details><summary>All 30 questions</summary><div class='wrap'><table><tr><th>ID</th><th>Question</th><th>Outcome</th>"
                 f"<th>Citation support</th></tr>{q_rows}</table></div></details></div></div>")

    v_rows = "".join(f"<tr><td>{e(x['name'])}</td><td>{e(x['base']['calc'])}</td></tr>" for x in val["rows"])
    meas = "".join(f"<tr><td>{e(m['name'])}</td><td>{e(m['kind'])}</td><td>{e(m['source'])}</td></tr>" for m in val["measures"])
    parts.append(f"<h2>Value: hours first, with the range and the assumptions</h2><p class='mute'>{e(val['label'])}</p>"
                 f"<div class='grid'><div class='card'><div class='mute'>Hours saved per deal (low / base / high)</div><div class='big'>"
                 f"{val['per_deal']['low']} / {val['per_deal']['base']} / {val['per_deal']['high']}</div><div class='mute'>"
                 f"{val['per_year']['low']}–{val['per_year']['high']} hours a year at {val['deals_per_year']} deals in diligence</div>"
                 f"<div class='wrap'><table><tr><th>Activity</th><th>Base case</th></tr>{v_rows}</table></div></div>"
                 f"<div class='card'><h3>Measured alongside</h3><div class='wrap'><table><tr><th>Measure</th><th>Kind</th><th>Source</th></tr>{meas}"
                 f"</table></div></div></div>")
    parts.append(f"<p class='mute' style='margin-top:32px'>Data as of {e(latest_date(ctx))} · evidence fingerprint "
                 f"<code>{e(ctx['evidence_fingerprint'][:16])}</code> · synthetic data, illustrative policies, personal prototype.</p></main></body></html>")
    return "".join(parts)
