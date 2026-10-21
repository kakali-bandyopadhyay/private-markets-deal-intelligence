"""Command line: python -m dealintel <command> ...  (synthetic data, illustrative policies)."""
from __future__ import annotations

import argparse
import json
import sys

from . import conflicts as cf
from . import graph as gr
from . import screening as sc
from .data import fmt, load


def _vals(ctx, metric, xs):
    return ", ".join(f"{fmt(ctx, metric, x['value'])} ({x['passage']})" for x in xs) or "none"


def _model(llm, max_cost):
    key = llm.api_key()
    if not key:
        raise SystemExit("Model mode needs OPENAI_API_KEY in the environment or in a git-ignored .env file "
                         "(see .env.example). The default no-key mode needs nothing.")
    cfg = llm.config()
    return llm.Budget(cfg, max_cost), llm.openai_client(key, cfg)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="dealintel", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("screen", help="screen a deal against the thesis")
    s.add_argument("deal"); s.add_argument("--as-of"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("conflicts", help="source conflicts for a deal's company")
    s.add_argument("deal"); s.add_argument("--as-of")
    s = sub.add_parser("changes", help="what changed in the evidence between two dates")
    s.add_argument("deal"); s.add_argument("--from", dest="date_from", required=True); s.add_argument("--to", dest="date_to")
    s = sub.add_parser("diff", help="fact-level diff between two document versions")
    s.add_argument("old"); s.add_argument("new")
    s = sub.add_parser("comparables", help="comparable companies through shared linked attributes")
    s.add_argument("company"); s.add_argument("-k", type=int, default=5)
    s = sub.add_parser("lineage", help="trace one fact to its passage, document version, deal and company")
    s.add_argument("fact")
    s = sub.add_parser("ask", help="ask a diligence question (answers cite passages)")
    s.add_argument("deal"); s.add_argument("question"); s.add_argument("--as-of")
    s.add_argument("--model", action="store_true", help="optional: phrase the answer with the configured model")
    s = sub.add_parser("eval", help="run the prototype evaluation set")
    s.add_argument("--out")
    s.add_argument("--model", action="store_true", help="optional: evaluate model mode (uses your API key, capped)")
    s.add_argument("--max-cost", type=float, help="USD cap for this run (default in data/model_config.json)")
    s.add_argument("--questions", help="question file (default data/eval/questions.json); use data/eval/heldout.json "
                                       "for the held-out set")
    s = sub.add_parser("memo", help="build the IC memo, run the gate and show the recorded human IC decision")
    s.add_argument("deal"); s.add_argument("--out")
    s = sub.add_parser("dashboard", help="write the static dashboard (docs/index.html)")
    s.add_argument("--out", default="docs/index.html")
    sub.add_parser("value", help="hours-saved estimate with range and assumptions")
    sub.add_parser("graph", help="graph size by node and edge type")
    sub.add_parser("fingerprint", help="SHA-256 of the input data")
    a = p.parse_args(argv)
    ctx = load()

    if a.cmd == "screen":
        r = sc.screen(ctx, a.deal, a.as_of)
        print(json.dumps(r, indent=2) if a.json else sc.as_text(r))
    elif a.cmd == "conflicts":
        company = ctx["deals"][a.deal]["company"]
        xs = cf.detect(ctx, company, a.as_of)
        print(f"Source conflicts for {a.deal} ({len(xs)})")
        for c in xs:
            print(f"  {c['id']}: {ctx['metrics'][c['metric']]['name']} {c['period']}")
            for s_ in c["sources"]:
                print(f"      {fmt(ctx, c['metric'], s_['value']):<10} {s_['passage']}" + (f"  [{s_['basis']}]" if s_["basis"] else ""))
    elif a.cmd == "changes":
        company = ctx["deals"][a.deal]["company"]
        from .data import latest_date
        to = a.date_to or latest_date(ctx)
        print(f"Evidence changes for {a.deal}: {a.date_from} -> {to}")
        for c in gr.changes(ctx, company, a.date_from, to):
            print(f"  {ctx['metrics'][c['metric']]['name']} ({c['period']}): {_vals(ctx, c['metric'], c['before'])}"
                  f"  ->  {_vals(ctx, c['metric'], c['after'])}   [{c['why']}]")
    elif a.cmd == "diff":
        print(f"Fact-level diff {a.old} -> {a.new}")
        for d in gr.version_diff(ctx, a.old, a.new):
            o = fmt(ctx, d["metric"], d["old"]["value"]) if d["old"] else "absent"
            n = fmt(ctx, d["metric"], d["new"]["value"]) if d["new"] else "absent"
            print(f"  {ctx['metrics'][d['metric']]['name']} ({d['period']}): {o} -> {n}"
                  + (f"   [{d['new']['basis']}]" if d["new"] and d["new"]["basis"] else ""))
    elif a.cmd == "comparables":
        g = gr.build(ctx)
        for c in gr.comparables(ctx, g, a.company, a.k):
            print(f"  {c['score']:>2}  {c['company']:<10} {c['name']}")
            for w in c["why"]:
                print(f"        - {w}")
    elif a.cmd == "lineage":
        g = gr.build(ctx)
        print("\n".join(gr.lineage(ctx, g, a.fact)))
    elif a.cmd == "ask":
        from . import qa
        if a.model:
            from . import llm
            budget, client = _model(llm, None)
            r = llm.answer(ctx, a.deal, a.question, a.as_of, client=client, budget=budget)
            print(qa.as_text(r))
            for x in r["rejected"]:
                print(f"  rejected claim: {x['text']} ({x['reason']})")
            print(f"  model calls {budget.calls}, estimated cost ${budget.spent:.4f}")
        else:
            print(qa.as_text(qa.answer(ctx, a.deal, a.question, a.as_of)))
    elif a.cmd == "eval":
        from pathlib import Path
        from . import evaluate as ev
        qs = ev.load_questions(Path(a.questions) if a.questions else None)
        held = bool(a.questions and "heldout" in a.questions)
        if a.model:
            from . import llm
            budget, client = _model(llm, a.max_cost)
            res = ev.run(ctx, qs, answer_fn=lambda q: llm.answer(ctx, q["deal"], q["question"], q.get("as_of"),
                                                             client=client, budget=budget))
            mode = f"model {budget.cfg['model']}, {budget.calls} calls, est. ${budget.spent:.4f}"
        else:
            res, mode = ev.run(ctx, qs), "no-key"
        name = "eval_heldout" if held else "eval_results"
        out = Path(a.out or f"out/{name}{'_model' if a.model else ''}.md")
        mode += f" mode, code at commit {ev.commit()}"
        label = (f"Held-out set of {len(qs)} questions not seen by the builder (authorship recorded in the question file); run once, "
                 "rules not tuned to it. Small set – not investment-grade validation." if held else None)
        md = ev.as_markdown(res, mode, label)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(md.split("By category")[0] + f"Per-question table: {out}")
    elif a.cmd == "memo":
        from pathlib import Path
        from . import memo as mm
        r = mm.build(ctx, a.deal)
        out = Path(a.out or f"out/memo_{a.deal}.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(r["markdown"], encoding="utf-8")
        print(f"{a.deal} memo v{r['memo']['version']}: {r['gate']['status']}")
        for c in r["gate"]["checks"]:
            print(f"  {c['id']} {'pass' if c['passed'] else 'FAIL'}  {c['name']}")
            for f in c["failures"]:
                print(f"        - {f}")
        d = r["decision"]
        print(f"  IC decision (human): {d['state']}" + (f" - {d['record']['decision']} by {d['record']['decided_by']}" if d.get("record") else "")
              + (f" ({d['why']})" if d.get("why") else ""))
        print(f"  memo written to {out}; fingerprint {r['fingerprint'][:16]}")
    elif a.cmd == "dashboard":
        from pathlib import Path
        from . import dashboard
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(dashboard.build(ctx), encoding="utf-8")
        print(f"dashboard written to {a.out}")
    elif a.cmd == "value":
        from . import value
        print(value.as_text(value.estimate()))
    elif a.cmd == "graph":
        print(json.dumps(gr.build(ctx).stats(), indent=2))
    elif a.cmd == "fingerprint":
        print(ctx["fingerprint"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
