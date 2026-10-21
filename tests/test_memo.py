import json
import shutil

import pytest

from dealintel import memo
from dealintel.data import DATA, load


@pytest.fixture()
def copy(tmp_path):
    d = tmp_path / "data"
    shutil.copytree(DATA, d)
    return d


def edit(path, fn):
    obj = json.loads(path.read_text(encoding="utf-8"))
    fn(obj)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def failures(r):
    return {c["id"]: c["failures"] for c in r["gate"]["checks"] if not c["passed"]}


def test_larkspur_memo_is_ready_and_the_ic_decision_is_recorded_by_a_person():
    r = memo.build(load(), "D-LARK")
    assert r["gate"]["status"] == memo.READY
    assert r["decision"]["state"] == "RECORDED" and "synthetic" in r["decision"]["record"]["decided_by"]


def test_osier_memo_is_blocked_for_four_separate_reasons():
    r = memo.build(load(), "D-OSIER")
    f = failures(r)
    assert r["gate"]["status"] == memo.BLOCKED and set(f) == {"G1", "G3", "G4", "G5"}
    assert "O04: no passage ID" in f["G1"]
    assert any("unresolved conflict CF-OSIER-net_revenue_retention" in x for x in f["G3"])
    assert r["decision"]["state"] == "NO DECISION RECORDED"


def test_accepted_conflicts_stay_visible():
    md = memo.build(load(), "D-LARK")["markdown"]
    assert md.count("accepted – sources still disagree") == 3


def test_removing_a_conflict_decision_blocks_the_claims_that_depend_on_it(copy):
    edit(copy / "conflict_decisions.json", lambda o: o["records"].pop(2))  # the NRR decision
    f = failures(memo.build(load(copy), "D-LARK"))
    assert f == {"G3": ["L06: depends on unresolved conflict CF-LARK-net_revenue_retention-FY2025"]}


def test_a_conflict_marked_not_usable_blocks_its_claims(copy):
    edit(copy / "conflict_decisions.json", lambda o: o["records"][0].update(memo_use="EXCLUDED"))
    assert "L03" in failures(memo.build(load(copy), "D-LARK"))["G3"][0]


def test_citing_a_replaced_version_is_blocked(copy):
    edit(copy / "memo" / "D-LARK.json", lambda o: o["claims"][1].update(passage_ids=["LARK-CIM@v1#p2"]))
    assert "replaced by a later version" in failures(memo.build(load(copy), "D-LARK"))["G2"][0]


def test_red_flag_without_due_date_blocks(copy):
    edit(copy / "red_flags.json", lambda o: o["records"][0].update(due=None))
    assert failures(memo.build(load(copy), "D-LARK"))["G4"] == ["RF-L1: no due date"]


def test_changing_the_memo_makes_the_ic_decision_stale(copy):
    edit(copy / "memo" / "D-LARK.json", lambda o: o["claims"][4].update(text="Cash conversion was strong."))
    assert memo.build(load(copy), "D-LARK")["decision"]["state"] == "STALE"


def test_recording_the_ic_decision_does_not_change_the_memo_fingerprint(copy):
    before = memo.build(load(copy), "D-LARK")["fingerprint"]
    edit(copy / "ic_decisions.json", lambda o: o["records"][0].update(rationale="edited"))
    assert memo.build(load(copy), "D-LARK")["fingerprint"] == before


def test_proceed_on_a_blocked_memo_is_invalid(copy):
    fp = memo.build(load(copy), "D-OSIER")["fingerprint"]
    edit(copy / "ic_decisions.json", lambda o: o["records"].append(
        {"deal": "D-OSIER", "decision": "PROCEED", "decided_by": "IC chair (synthetic role)", "at": "2026-06-01T10:00:00Z",
         "rationale": "x", "memo_fingerprint": fp}))
    d = memo.build(load(copy), "D-OSIER")["decision"]
    assert d["state"] == "INVALID" and "passed the gate" in d["why"]


def test_request_more_work_on_a_blocked_memo_is_allowed(copy):
    fp = memo.build(load(copy), "D-OSIER")["fingerprint"]
    edit(copy / "ic_decisions.json", lambda o: o["records"].append(
        {"deal": "D-OSIER", "decision": "REQUEST MORE WORK", "decided_by": "IC chair (synthetic role)",
         "at": "2026-06-01T10:00:00Z", "rationale": "Resolve NRR and assign the tax red flag.", "memo_fingerprint": fp}))
    assert memo.build(load(copy), "D-OSIER")["decision"]["state"] == "RECORDED"


def test_expert_call_only_claim_must_be_labelled_unverified(copy):
    edit(copy / "memo" / "D-LARK.json", lambda o: next(c for c in o["claims"] if c["id"] == "L11").pop("evidence_label"))
    assert failures(memo.build(load(copy), "D-LARK")) == {
        "G6": ["L11: rests only on expert-call claims; label it an unverified lead"]}


def test_unverified_leads_are_shown_as_such_and_red_flags_carry_a_treatment():
    md = memo.build(load(), "D-LARK")["markdown"]
    assert "**Unverified lead:** One expert heard" in md
    assert "Assess – plan and cost, not a blocker on its own" in md


def test_adding_an_evaluation_file_does_not_make_the_ic_decision_stale(copy):
    (copy / "eval" / "heldout_run9.json").write_text('{"questions": []}\n', encoding="utf-8")
    assert memo.build(load(copy), "D-LARK")["decision"]["state"] == "RECORDED"
