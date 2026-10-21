"""Value estimate: analyst hours per deal and per year, with a low-base-high range and every assumption shown.

Hours come first; quality and adoption measures sit beside them so the value story is not only an hours estimate.
The assumptions are illustrative (data/value_assumptions.json) and would be replaced by timed pilot measurements.
"""
from __future__ import annotations

import json

from .data import DATA

CASES = ("low", "base", "high")


def assumptions() -> dict:
    return json.loads((DATA / "value_assumptions.json").read_text(encoding="utf-8"))


def estimate(a: dict | None = None) -> dict:
    a = a or assumptions()
    rows, totals = [], {c: 0.0 for c in CASES}
    for x in a["activities"]:
        r = {"id": x["id"], "name": x["name"], "why": x["why"]}
        for c in CASES:
            v = x["volume_per_deal"][c]
            saved = v * (x["minutes_before"][c] - x["minutes_after"][c]) / 60
            r[c] = {"volume": v, "before_min": x["minutes_before"][c], "after_min": x["minutes_after"][c],
                    "hours_saved_per_deal": round(saved, 1),
                    "calc": f"{v} x ({x['minutes_before'][c]} - {x['minutes_after'][c]}) min / 60 = {saved:.1f} h"}
            totals[c] += saved
        rows.append(r)
    n = a["deals_in_diligence_per_year"]
    return {"label": a["label"], "rows": rows, "deals_per_year": n,
            "per_deal": {c: round(totals[c], 1) for c in CASES},
            "per_year": {c: round(totals[c] * n) for c in CASES}, "measures": a["measures"]}


def as_text(e: dict) -> str:
    out = [f"Value estimate ({e['label']})"]
    for r in e["rows"]:
        out.append(f"  {r['name']}: " + "; ".join(f"{c} {r[c]['calc']}" for c in CASES))
    out.append(f"  Hours saved per deal: low {e['per_deal']['low']}, base {e['per_deal']['base']}, high {e['per_deal']['high']}")
    out.append(f"  Per year at {e['deals_per_year']} deals in diligence: low {e['per_year']['low']}, base {e['per_year']['base']}, "
               f"high {e['per_year']['high']} hours")
    out.append("  Measured alongside: " + "; ".join(f"{m['name']} ({m['kind']})" for m in e["measures"]))
    return "\n".join(out)
