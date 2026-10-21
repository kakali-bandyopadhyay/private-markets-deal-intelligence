"""Fixes for the causes found in held-out run 2 (docs/FINDINGS.md), tested with new phrasings."""
import pytest

from dealintel import qa
from dealintel.data import load


@pytest.fixture(scope="module")
def ctx():
    return load()


def test_weak_passage_match_falls_back_to_the_figure_and_its_conflict(ctx):
    r = qa.answer(ctx, "D-LARK", "Does NRR clear the bar after removing the one-off telematics sale to the top account?")
    assert r["status"] == "CONFLICTED"
    assert {"LARK-CIM@v2#p4", "LARK-COHORT@v1#p2"} <= set(r["citations"])


def test_generic_words_alone_do_not_make_a_match(ctx):
    r = qa.answer(ctx, "D-LARK", "What was the year-end net debt figure?")
    assert r["status"] == "INSUFFICIENT" and not r["citations"]


def test_version_explanation_is_cited_only_when_it_is_about_the_metric(ctx):
    r = qa.answer(ctx, "D-LARK", "Did the recurring revenue share change in the restated memorandum?")
    assert r["status"] == "CHANGED" and "LARK-CIM@v2#p1" not in r["citations"]
    r = qa.answer(ctx, "D-LARK", "Why was revenue restated?")
    assert "LARK-CIM@v2#p1" in r["citations"]
