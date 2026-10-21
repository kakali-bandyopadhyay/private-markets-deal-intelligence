import pytest

from dealintel import evaluate as ev
from dealintel import qa
from dealintel.data import load


@pytest.fixture(scope="module")
def ctx():
    return load()


def test_conflicting_sources_are_shown_not_resolved(ctx):
    r = qa.answer(ctx, "D-LARK", "What is net revenue retention?")
    assert r["status"] == "CONFLICTED"
    assert {c["value"] for c in r["claims"]} == {1.12, 1.04}


def test_changed_version_shows_old_value_as_superseded_with_explanation(ctx):
    r = qa.answer(ctx, "D-LARK", "Why was revenue restated?")
    roles = {c["role"]: c for c in r["claims"]}
    assert r["status"] == "CHANGED"
    assert roles["superseded"]["passage_ids"] == ["LARK-CIM@v1#p2"]
    assert roles["explanation"]["passage_ids"] == ["LARK-CIM@v2#p1"]


def test_as_of_date_answers_with_what_was_known_then(ctx):
    r = qa.answer(ctx, "D-LARK", "What was revenue?", as_of="2026-05-12")
    assert r["status"] == "SUPPORTED" and r["citations"] == ["LARK-CIM@v1#p2"]


def test_similar_name_and_other_companies_are_declined(ctx):
    for q in ("What revenue did Larkspur Analytics report?", "What was Rowan's revenue?"):
        r = qa.answer(ctx, "D-LARK", q)
        assert r["status"] == "INSUFFICIENT" and r["citations"] == []


def test_wrong_number_from_another_company_is_not_echoed(ctx):
    r = qa.answer(ctx, "D-LARK", "Did Larkspur's retention improve to 120%?")
    assert not any(p.startswith("NEWS-") for p in r["citations"])
    assert 1.20 not in {c["value"] for c in r["claims"]}


def test_missing_period_is_insufficient_not_nearest_year(ctx):
    assert qa.answer(ctx, "D-LARK", "What was FY2024 revenue?")["status"] == "INSUFFICIENT"


def test_text_question_mentioning_a_metric_goes_to_the_passage(ctx):
    r = qa.answer(ctx, "D-LARK", "Does the contract with the largest customer contain a change-of-control clause?")
    assert r["citations"] == ["LARK-LEGAL@v1#p1"]


def test_weak_keyword_overlap_is_declined(ctx):
    r = qa.answer(ctx, "D-LARK", "What is the gross margin?")
    assert r["status"] == "INSUFFICIENT" and "not cited" in r["notes"][0]


@pytest.mark.parametrize("claim,reason", [
    ({"text": "x", "passage_ids": []}, "no passage ID"),
    ({"text": "x", "passage_ids": ["LARK-CIM@v9#p1"]}, "invalid"),
    ({"text": "x", "passage_ids": ["OSIER-CIM@v1#p1"]}, "invalid"),          # another deal
    ({"text": "x", "passage_ids": ["NEWS-0520@v1#p1"]}, "invalid"),          # not a deal document
    ({"text": "x", "passage_ids": ["LARK-QOE@v1#p2"]}, "invalid"),           # dated after the as-of date
])
def test_citation_validator_rejects(ctx, claim, reason):
    kept, rejected = qa.validate_citations(ctx, "D-LARK", "2026-06-30", [claim])
    assert not kept and reason in rejected[0]["reason"]


def test_citation_validator_limits_to_retrieved_passages(ctx):
    c = {"text": "x", "passage_ids": ["LARK-MP@v1#p1"]}
    assert qa.validate_citations(ctx, "D-LARK", "2026-08-05", [c], allowed={"LARK-MP@v1#p1"})[0] == [c]
    assert qa.validate_citations(ctx, "D-LARK", "2026-08-05", [c], allowed={"LARK-MKT@v1#p1"})[1]


def test_evaluation_reports_measures_separately_and_per_question(ctx):
    res = ev.run(ctx)
    assert res["summary"]["questions"] == 30 and len(res["rows"]) == 30
    cats = {r["category"] for r in res["rows"]}
    assert cats == {"supported", "insufficient", "conflicting", "changed_version", "misleading"}
    assert all(sum(r["category"] == c for r in res["rows"]) == 6 for c in cats)
    assert "not investment-grade" in res["summary"]["label"].lower()


def test_scorer_catches_a_wrong_citation(ctx):
    q = ev.load_questions()[0]
    bad = {"status": "SUPPORTED", "citations": ["LARK-MKT@v1#p1"], "claims": [{"value": 88.0, "passage_ids": ["LARK-MKT@v1#p1"]}]}
    s = ev.score(ctx, q, bad)
    assert s["citation_valid"] and not s["citation_support"]
