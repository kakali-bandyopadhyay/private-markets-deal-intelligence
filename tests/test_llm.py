"""Model mode is tested with fake clients only. No test calls the API."""
import json
from pathlib import Path

import pytest

from dealintel import evaluate as ev
from dealintel import llm
from dealintel.data import ROOT, load


@pytest.fixture(scope="module")
def ctx():
    return load()


def fake(answer):
    calls = []

    def client(payload):
        calls.append(payload)
        ids = [p["id"] for p in json.loads(payload["input"])["passages"]]
        out = answer(ids)
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(out)}]}],
                "usage": {"input_tokens": 1200, "output_tokens": 150}}
    client.calls = calls
    return client


def budget(cap=0.5):
    return llm.Budget(llm.config(), cap)


def test_valid_claims_are_kept_and_cited(ctx):
    c = fake(lambda ids: {"status": "SUPPORTED", "claims": [{"text": "Gross logo churn was 6%.", "passage_ids": [ids[0]]}]})
    r = llm.answer(ctx, "D-LARK", "What was gross logo churn?", client=c, budget=budget())
    assert r["status"] == "SUPPORTED" and r["citations"] == ["LARK-COHORT@v1#p3"] and not r["rejected"]


def test_claims_citing_outside_the_evidence_pack_are_rejected(ctx):
    c = fake(lambda ids: {"status": "SUPPORTED", "claims": [
        {"text": "Churn was 6%.", "passage_ids": [ids[0]]},
        {"text": "Retention improved to 120%.", "passage_ids": ["NEWS-0520@v1#p1"]},
        {"text": "Unsupported.", "passage_ids": []}]})
    r = llm.answer(ctx, "D-LARK", "What was gross logo churn?", client=c, budget=budget())
    assert len(r["claims"]) == 1 and len(r["rejected"]) == 2
    assert "NEWS-0520@v1#p1" not in r["citations"]


def test_answer_withheld_when_no_claim_survives_validation(ctx):
    c = fake(lambda ids: {"status": "SUPPORTED", "claims": [{"text": "x", "passage_ids": ["MADE-UP#p1"]}]})
    r = llm.answer(ctx, "D-LARK", "What was gross logo churn?", client=c, budget=budget())
    assert r["status"] == "INSUFFICIENT" and "withheld" in r["notes"][0]


def test_out_of_scope_company_is_declined_without_a_model_call(ctx):
    c = fake(lambda ids: {"status": "SUPPORTED", "claims": []})
    r = llm.answer(ctx, "D-LARK", "What revenue did Larkspur Analytics report?", client=c, budget=budget())
    assert r["status"] == "INSUFFICIENT" and c.calls == []


def test_budget_stops_the_run_before_an_expensive_call(ctx):
    c = fake(lambda ids: {"status": "INSUFFICIENT", "claims": []})
    with pytest.raises(llm.BudgetExceeded):
        llm.answer(ctx, "D-LARK", "What was gross logo churn?", client=c, budget=budget(0.0001))
    assert c.calls == []


def test_payload_pins_the_model_and_asks_for_structured_output(ctx):
    c = fake(lambda ids: {"status": "INSUFFICIENT", "claims": []})
    llm.answer(ctx, "D-LARK", "What was gross logo churn?", client=c, budget=budget())
    p = c.calls[0]
    assert p["model"] == "gpt-5.4-mini-2026-03-17"
    assert p["text"]["format"]["type"] == "json_schema" and p["text"]["format"]["strict"] is True
    assert "Do not recommend investment decisions" in p["instructions"]


def test_superseded_passages_are_labelled_in_the_evidence_pack(ctx):
    pack = llm.evidence_pack(ctx, "D-LARK", "How did revenue change between the first and second information memorandum?", "2026-08-05")
    v1 = next(p for p in pack if p["id"] == "LARK-CIM@v1#p2")
    assert "SUPERSEDED" in v1["source"]


def test_model_mode_runs_through_the_same_evaluation(ctx):
    c = fake(lambda ids: {"status": "INSUFFICIENT", "claims": []})
    res = ev.run(ctx, answer_fn=lambda q: llm.answer(ctx, q["deal"], q["question"], q.get("as_of"), client=c, budget=budget(5)))
    n = sum(q["expected_status"] == "INSUFFICIENT" for q in ev.load_questions())
    assert res["summary"]["appropriate_refusal"].startswith(f"{n}/{n}")


def test_key_is_never_committed():
    ignore = (ROOT / ".gitignore").read_text()
    assert ".env" in ignore.splitlines()
    assert (ROOT / ".env.example").read_text().strip().endswith("OPENAI_API_KEY=")


def test_unreadable_model_output_is_withheld_not_crashed(ctx):
    def client(payload):
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": "{not json"}]}],
                "usage": {"input_tokens": 10, "output_tokens": 10}}
    r = llm.answer(ctx, "D-LARK", "What was gross logo churn?", client=client, budget=budget())
    assert r["status"] == "INSUFFICIENT" and r["reason"] == "model_error"
