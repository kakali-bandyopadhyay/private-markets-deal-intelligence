"""Fixes for the causes found in held-out run 1 (docs/FINDINGS.md), tested with new phrasings."""
import pytest

from dealintel import qa
from dealintel.data import load


@pytest.fixture(scope="module")
def ctx():
    return load()


@pytest.mark.parametrize("q", ["What were quarterly EBITDA figures?", "What is the revenue backlog?"])
def test_figure_narrower_than_the_sourced_figure_is_declined(ctx, q):
    r = qa.answer(ctx, "D-LARK", q)
    assert r["status"] == "INSUFFICIENT" and r["reason"] == "no_evidence" and not r["citations"]


def test_passage_answers_still_go_through_the_conflict_check(ctx):
    r = qa.answer(ctx, "D-LARK", "What does the cohort analysis say about the telematics bundle and retention?")
    assert r["status"] == "CONFLICTED"
    assert {"LARK-CIM@v2#p4", "LARK-MP@v1#p1", "LARK-COHORT@v1#p2"} <= set(r["citations"])


def test_one_interview_does_not_answer_a_question_about_the_customer_base(ctx):
    r = qa.answer(ctx, "D-LARK", "How many of the customers would tolerate a price rise?")
    assert r["status"] == "INSUFFICIENT" and not r["citations"]


def test_updated_document_wording_uses_version_history(ctx):
    r = qa.answer(ctx, "D-LARK", "Was EBITDA updated in the second CIM?")
    assert r["status"] == "CHANGED" and "LARK-CIM@v1#p3" in r["citations"]


def test_synonyms_bridge_a_paraphrase(ctx):
    r = qa.answer(ctx, "D-LARK", "What growth drivers did management describe?")
    assert r["status"] == "SUPPORTED" and r["citations"] == ["LARK-MP@v1#p3"]
