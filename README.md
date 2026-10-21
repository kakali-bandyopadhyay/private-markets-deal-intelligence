# Private-markets deal intelligence

**From screening to an evidence-backed IC memo for human review.** A personal prototype of one narrow product workflow
for a private-markets deal team: screen a company against configurable criteria, answer diligence questions with
citations, surface conflicting and changed evidence, and gate the IC memo so that only cited, reconciled and owned
material reaches the investment committee. The investment decision stays with people and is recorded against the exact
memo version.

> **Prototype labels.** All companies, documents and figures are synthetic; code names are invented. Screening criteria
> and policies are illustrative. This project is not connected to, or based on, any firm's systems or processes.
> Evaluation results are from a small hand-authored set and are not investment-grade validation.

Dashboard: `docs/index.html` (one deal end to end, the blocked contrast case, evaluation and value).

## The workflow (one deal: Project Larkspur)

| Step | What the system does | What a person decides |
|---|---|---|
| 1. Screening (12 May) | Shows each criterion as MET / NOT MET / UNKNOWN / CONFLICTED with the passage behind every value – no composite score; a conflicted criterion is never treated as passed | Advance, hold or decline (`data/screening_decisions.json`) |
| 2. Evidence changes | Shows what changed between document versions and dates (restated revenue, new adviser reports) | – |
| 3. Diligence Q&A | Answers from the deal's live documents only, every claim cited; shows conflicts instead of picking; declines when evidence is missing or the question is about another company | – |
| 4. Conflicts | Detects live sources that disagree (recurring revenue 80% vs 71%, EBITDA 24 vs 21.5, NRR 112% vs 104%) | Accept with a base case and rationale; the conflict stays visible (`data/conflict_decisions.json`) |
| 5. IC memo gate | Six checks: valid citations, no replaced versions, decisions on conflicted facts, owned red flags, maker-checker, expert-call-only claims labelled as unverified leads | Red-flag owner, due date and treatment (investigate or assess – not automatic disqualifiers) |
| 6. IC decision | Verifies the record matches the memo fingerprint and that PROCEED only follows a READY memo | Proceed, decline or request more work (`data/ic_decisions.json`) |

Two supporting cases give contrast: **Project Bramble** stops at screening on unknowns, and **Project Osier** is blocked
at the memo gate (uncited claim, unresolved conflict, unowned red flag, same drafter and reviewer).

## Run it

Python 3.11+, no runtime dependencies.

```bash
python -m venv .venv && . .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q

python -m dealintel screen D-LARK --as-of 2026-05-12   # screening on the first memorandum
python -m dealintel screen D-LARK                      # after diligence: conflicts, not a single number
python -m dealintel changes D-LARK --from 2026-05-12   # what changed in the evidence, and why
python -m dealintel diff LARK-CIM@v1 LARK-CIM@v2       # fact-level diff between versions
python -m dealintel ask D-LARK "What is net revenue retention?"
python -m dealintel ask D-LARK "What revenue did Larkspur Analytics report?"   # declined: different company
python -m dealintel memo D-LARK                        # READY FOR IC REVIEW + recorded human decision
python -m dealintel memo D-OSIER                       # BLOCKED, four reasons
python -m dealintel eval                               # 30-question prototype evaluation
python -m dealintel value                              # hours estimate with range and assumptions
python -m dealintel comparables C-LARK
python -m dealintel lineage "LARK-COHORT@v1#p2/f1"
python -m dealintel dashboard
```

### Optional model mode

The default no-key mode is deterministic and is what the tests and published results use. Model mode phrases answers
with an OpenAI model **from the retrieved passages only**:

- copy `.env.example` to `.env` (git-ignored) and set `OPENAI_API_KEY`; never commit `.env`;
- the model is pinned in `data/model_config.json` and each run has a cost cap (default USD 0.50);
- the model returns structured claims with passage IDs; claims with a missing ID, or an ID outside the evidence pack,
  are rejected (**citation validation, not fact verification** – support is assessed in the evaluation);
- the model never selects deals, resolves conflicts or approves the memo; tests use fake clients and never call the API.

```bash
python -m dealintel ask D-LARK "What is net revenue retention?" --model
python -m dealintel eval --model --max-cost 0.50
```

## Evidence classes

Every document carries an evidence class – management representation, adviser finding, deal-team analysis, expert-call
claim, third-party publication or internal data – shown with answers and used by the gate: a memo claim that rests only
on expert-call claims must be labelled an unverified lead to verify through permitted diligence.

## What the knowledge graph adds, and what is plain search

The graph (`graph.py`) links companies, attributes, deals, document versions, passages, facts, metrics and memo claims.
It is used where a question needs links or history:

1. **What changed between versions or dates?** (`changes`, `diff`: SUPERSEDES edges and fact values)
2. **Which memo claims depend on a conflicted fact?** (DEPENDS_ON edges; drives gate check G3)
3. **Which companies are comparable, and why?** (shared attribute nodes plus a sourced revenue band)

Finding the passage that answers a question is keyword search (BM25 in `search.py`), not a graph feature.

## Evaluation (prototype)

`data/eval/questions.json`: 30 hand-authored questions, six in each of five types – supported, insufficient evidence,
conflicting sources, changed version, misleading or irrelevant evidence – each with the expected outcome and the
expected source passages. Measures are reported separately and per question: outcome, citation validity (the passage
exists and is in scope), citation support (the cited passages match the hand-labelled supporting passages), appropriate
refusal (and whether it was refused for the right reason) and conflict detection.

All questions are asked in one fixed active deal scope. A refusal carries a reason – `no_evidence`, `wrong_entity` (a
similarly named, unrelated company, or a figure that belongs to one) or `out_of_scope` (another company that is not in
the active deal) – kept separate from CONFLICTED, which means relevant sources disagree about the same target fact.

The rules were developed alongside this set, so its results are optimistic. `data/eval/heldout.json` holds questions
prepared without access to the rules (authorship per run in `docs/FINDINGS.md`); protocol: freeze the code, record the commit, run once
(`python -m dealintel eval --questions data/eval/heldout.json`), report by question type with misses and reasons, and
do not tune to it afterwards.

**Held-out results, reported separately:** run 1 – 4/10 correct outcomes (12/12 citations resolved; two answers that
should have been refusals); run 2, new unseen questions after fixing run 1's causes – 6/8 (12/12 citations resolved;
one false conflict, one missed conflict, one unsupported citation). Run 1 questions were AI-drafted and reviewed by the
owner; run 2 questions were prepared by an AI assistant that had not inspected the implementation. Misses, causes and
fixes are in `docs/FINDINGS.md`; run 3 will use human-drafted, human-reviewed questions.

## Repository map

| Path | Purpose |
|---|---|
| `data/documents/` | 18 synthetic documents (62 passages, hand-tagged facts); one document has two versions |
| `data/thesis.json` | Illustrative, versioned screening criteria and screening rule |
| `data/memo/`, `conflict_decisions.json`, `red_flags.json`, `screening_decisions.json`, `ic_decisions.json` | Memo claims and human decision records (synthetic roles) |
| `data/eval/questions.json` | Prototype evaluation set |
| `src/dealintel/` | `screening`, `graph`, `conflicts`, `search`, `qa`, `memo`, `evaluate`, `value`, `llm`, `dashboard` |
| `docs/` | `TRADEOFFS.md`, `ARCHITECTURE.md`, `DEMO_SCRIPT.md`, dashboard |

## Limitations

Facts are hand-tagged (no automated extraction); single currency and fiscal year; keyword retrieval only; the value
estimate is built on stated assumptions, not measurements; synthetic roles stand in for people and access control.
See `docs/TRADEOFFS.md` for what v1 leaves out and why.

Licence: MIT.
