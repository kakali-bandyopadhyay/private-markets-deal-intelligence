"""Fixes for the causes found in held-out run 3 (docs/FINDINGS.md), tested with new phrasings."""
import pytest

from dealintel import qa
from dealintel.data import load


@pytest.fixture(scope="module")
def ctx():
    return load()


@pytest.mark.parametrize("q", ["If the owner sells, can the top customer walk away, and on what notice?",
                               "What rights does the biggest customer have under its contract if ownership changes?"])
def test_a_question_about_the_largest_customer_is_not_answered_with_its_revenue_share(ctx, q):
    r = qa.answer(ctx, "D-LARK", q)
    assert "LARK-COHORT@v1#p4" not in r["citations"]
    assert r["status"] == "INSUFFICIENT" or r["citations"] == ["LARK-LEGAL@v1#p1"]


def test_largest_customer_share_is_still_answered_when_asked(ctx):
    r = qa.answer(ctx, "D-LARK", "What is the largest customer share of revenue?")
    assert r["status"] == "SUPPORTED" and r["citations"] == ["LARK-COHORT@v1#p4"]


def test_hypothetical_recalculation_is_declined(ctx):
    r = qa.answer(ctx, "D-LARK", "What would EBITDA be if the office savings were excluded?")
    assert r["status"] == "INSUFFICIENT" and r["reason"] == "no_evidence" and not r["citations"]


def test_a_stated_adjusted_basis_is_still_answered(ctx):
    r = qa.answer(ctx, "D-LARK", "If we strip out the one-off bundle, what is net revenue retention?")
    assert r["status"] == "CONFLICTED"


def test_sales_is_read_as_revenue(ctx):
    r = qa.answer(ctx, "D-LARK", "Did FY2025 sales change in the second memorandum?")
    assert r["status"] == "CHANGED" and "LARK-CIM@v1#p2" in r["citations"]


def test_cost_paraphrase_reaches_the_remediation_passage(ctx):
    r = qa.answer(ctx, "D-LARK", "How much will it cost to fix the outdated framework code?")
    assert r["status"] == "SUPPORTED" and r["citations"] == ["LARK-TECH@v1#p3"]
