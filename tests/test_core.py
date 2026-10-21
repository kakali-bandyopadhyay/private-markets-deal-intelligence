import json
import shutil

import pytest

from dealintel import conflicts as cf
from dealintel import graph as gr
from dealintel import screening as sc
from dealintel.data import DATA, active_docs, fingerprint, load


@pytest.fixture(scope="module")
def ctx():
    return load()


@pytest.fixture(scope="module")
def g(ctx):
    return gr.build(ctx)


# ---------------------------------------------------------------- data
def test_every_fact_points_to_a_real_passage(ctx):
    assert ctx["facts"]
    for f in ctx["facts"]:
        assert f["passage"] in ctx["passages"]


def test_superseded_version_drops_out_only_after_the_new_version_date(ctx):
    assert "LARK-CIM@v1" in active_docs(ctx, "2026-05-12")
    assert "LARK-CIM@v1" not in active_docs(ctx, "2026-06-02")
    assert "LARK-CIM@v2" in active_docs(ctx, "2026-06-02")


def test_fingerprint_ignores_line_endings(tmp_path):
    copy = tmp_path / "data"
    shutil.copytree(DATA, copy)
    p = copy / "thesis.json"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert fingerprint(copy) == fingerprint(DATA)


def test_unknown_metric_is_rejected(tmp_path):
    copy = tmp_path / "data"
    shutil.copytree(DATA, copy)
    p = copy / "documents" / "LARK-MKT_v1.json"
    d = json.loads(p.read_text())
    d["paragraphs"][0]["facts"][0]["metric"] = "made_up"
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="unknown metric"):
        load(copy)


# ---------------------------------------------------------------- screening
def statuses(r):
    return {x["criterion"]: x["status"] for x in r["rows"]}


def test_larkspur_on_first_memorandum_advances_with_two_unknowns(ctx):
    r = sc.screen(ctx, "D-LARK", "2026-05-12")
    assert statuses(r) == {"REC": "MET", "EBITDA": "MET", "NRR": "MET", "CONC": "UNKNOWN", "FRAG": "UNKNOWN", "GEO": "MET"}
    assert r["open"] == 2 and r["outcome"].startswith("MEETS")


def test_larkspur_after_diligence_shows_conflicts_not_a_single_number(ctx):
    r = sc.screen(ctx, "D-LARK")
    s = statuses(r)
    assert s["REC"] == s["EBITDA"] == s["NRR"] == "CONFLICTED"
    nrr = next(x for x in r["rows"] if x["criterion"] == "NRR")
    assert nrr["open_question"] and {v["passes"] for v in nrr["evidence"]} == {True, False}
    rec = next(x for x in r["rows"] if x["criterion"] == "REC")
    assert not rec["open_question"], "a conflict where every source passes is not an open screening question"


def test_bramble_stops_on_unknowns_not_on_a_guess(ctx):
    r = sc.screen(ctx, "D-BRAM")
    assert sum(x["status"] == "UNKNOWN" for x in r["rows"]) == 4
    assert r["outcome"].startswith("NOT ENOUGH EVIDENCE")


def test_a_failing_value_is_not_met(ctx):
    ctx2 = dict(ctx, thesis=json.loads(json.dumps(ctx["thesis"])))
    next(c for c in ctx2["thesis"]["criteria"] if c["id"] == "EBITDA")["value"] = [20, 60]
    r = sc.screen(ctx2, "D-BRAM")
    assert statuses(r)["EBITDA"] == "NOT MET" and r["outcome"].startswith("DOES NOT MEET")


def test_screening_shows_the_human_decision_but_does_not_make_it(ctx):
    assert sc.screen(ctx, "D-BRAM", "2026-08-05")["decision"] is None
    d = sc.screen(ctx, "D-BRAM", "2026-08-06")["decision"]
    assert d["decision"].startswith("HOLD") and "synthetic" in d["decided_by"]


def test_unrelated_company_with_similar_name_is_never_used(ctx):
    r = sc.screen(ctx, "D-LARK")
    used = {v["passage"] for x in r["rows"] for v in x["evidence"]}
    assert not any(p.startswith("NEWS-") for p in used)


# ---------------------------------------------------------------- conflicts and graph
def test_conflicts_are_stable_and_exclude_superseded_versions(ctx):
    ids = {c["id"] for c in cf.detect(ctx, "C-LARK")}
    assert ids == {"CF-LARK-adj_ebitda_eur_m-FY2025", "CF-LARK-net_revenue_retention-FY2025",
                   "CF-LARK-recurring_revenue_share-FY2025"}
    assert cf.detect(ctx, "C-LARK", "2026-05-12") == []
    rev = [c for c in cf.detect(ctx, "C-LARK") if c["metric"] == "revenue_eur_m"]
    assert rev == [], "v1 revenue (92) was replaced by v2 (88), which the QoE agrees with"


def test_version_diff_lists_only_changed_facts(ctx):
    d = {x["metric"]: (x["old"]["value"], x["new"]["value"]) for x in gr.version_diff(ctx, "LARK-CIM@v1", "LARK-CIM@v2")}
    assert d == {"revenue_eur_m": (92.0, 88.0), "recurring_revenue_share": (0.78, 0.80), "adj_ebitda_eur_m": (26.0, 24.0)}


def test_changes_explain_why(ctx):
    ch = {c["metric"]: c for c in gr.changes(ctx, "C-LARK", "2026-05-12", "2026-07-10")}
    assert "superseded: LARK-CIM@v1#p2" in ch["revenue_eur_m"]["why"]
    assert "sources now disagree" in ch["net_revenue_retention"]["why"]
    assert ch["market_top3_share"]["why"] == "new evidence"
    assert "hq_country" not in ch


def test_comparables_rank_by_linked_attributes_with_reasons(ctx, g):
    top = gr.comparables(ctx, g, "C-LARK", 3)
    assert top[0]["company"] == "C-ROWAN"
    assert any("end_market = fleet and logistics" in w for w in top[0]["why"])
    assert all(c["company"] != "C-LARKUS" for c in top)


def test_lineage_walks_from_fact_to_company(ctx, g):
    steps = gr.lineage(ctx, g, "LARK-CIM@v2#p2/f1")
    assert steps[1].startswith("passage LARK-CIM@v2#p2")
    assert any(s.startswith("replaces LARK-CIM@v1") for s in steps)
    assert steps[-1].startswith("company C-LARK")


def test_claims_on_conflicts_follow_depends_on_edges(g):
    g2 = gr.Graph()
    g2.nodes, g2.edges = dict(g.nodes), list(g.edges)
    g2.node("CLAIM-1", "claim")
    g2.edge("CLAIM-1", "DEPENDS_ON", "LARK-COHORT@v1#p2/f1")
    got = gr.claims_on_conflicts(g2, {"CF-NRR": ["LARK-COHORT@v1#p2/f1", "LARK-MP@v1#p1/f1"]})
    assert got == {"CF-NRR": ["CLAIM-1"]}


def test_conflicted_criterion_is_never_reported_as_passed(ctx):
    r = sc.screen(ctx, "D-LARK")
    assert "never treated as passed" in r["conflicted_policy"]
    assert all(x["status"] != "MET" for x in r["rows"] if x["criterion"] in ("REC", "EBITDA", "NRR"))


def test_every_passage_carries_an_evidence_class(ctx):
    assert {p["evidence_class"] for p in ctx["passages"].values()} >= {
        "management representation", "adviser finding", "deal-team analysis", "expert-call claim"}
