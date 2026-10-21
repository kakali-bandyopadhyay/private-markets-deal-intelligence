# Findings

Run log (each run once, on a frozen build; scores are reported separately and never combined):

| Run | Questions | Code | Result |
|---|---|---|---|
| Development | 30, written alongside the rules | – | 30/30 (optimistic) |
| Held-out run 1 | 10, AI-drafted and reviewed by the owner (informed by earlier development-set misses) | 9cb20c6, run at 2f722ee (questions added, no code change) | **4/10** |
| Held-out run 2 | 8 new, prepared by an AI assistant that had not inspected the implementation; unseen by the builder | 197d4b1 | **6/8** |
| Held-out run 3 | 10 new, drafted from the source documents; expected labels reviewed by the owner against those documents before the run; not used to tune the implementation before it | frozen beab828, run at 96a201b (docs and an output label only) | **7/10** (one of the 7 has the right outcome but the wrong answer) |

## Held-out evaluation, run 1 (no-key mode)

Ten questions, AI-drafted and reviewed by the owner (informed by earlier development-set misses), phrased the way a deal team would ask; the builder had not seen them before the run. Expected
passages were labelled from the documents before the run. Code frozen at the commit recorded in `data/eval/heldout.json`;
questions added with no code or rule change; run once. Small set – not investment-grade validation.

| Measure | Development set (30, rules built alongside it) | Held-out set (10) |
|---|---|---|
| Correct outcome | 30/30 | **4/10** |
| Citations pointing to a real, in-scope passage | 41/41 | **12/12** |
| Cited passages match the labelled support | 19/19 | 2/6 |
| Declined when it should | 11/11 | 2/4 |
| Answered when it should have declined | 0 | **2** (H08, H10) |
| Conflicts shown | 6/6 | 0/2 |

The gap between 30/30 and 4/10 is the finding: the development score measured the rules against the questions they
were written for.

### What held

- No invented or out-of-scope citation in any answer (12/12 valid).
- The similarly named company's figure was refused for the right reason (H09).
- A version change phrased as "revised" was recognised (H05).

### Misses and why

| ID | Question (abridged) | Expected | Got | Cause |
|---|---|---|---|---|
| H08 | Revenue contracted to renew next year? | Decline | Total FY2025 revenue (EUR 88m) | **Answered a different question.** The word "revenue" matched the revenue figure; the qualifier ("contracted to renew next year") was ignored. Most serious miss. |
| H10 | Share of customers who would accept 6%? | Decline | One customer's 5% tolerance, as SUPPORTED | **Over-claim from one expert call.** Labelled as an expert-call claim, but one interview does not answer "what share of customers". |
| H03 | Retention without the one-off bundle? | Conflicted | One cohort passage, SUPPORTED | Descriptive words sent the question to passage search, which **skips the conflict check**; management's 112% source was not cited. |
| H04 | Treat implementation fees as recurring? | Conflicted | QoE passage, SUPPORTED | Same routing flaw; the passage contains both figures, but the outcome hides the disagreement. |
| H06 | EBITDA same in the updated CIM? | Changed | Conflicted (24 vs 21.5) | "Updated" and "CIM" are not in the change vocabulary; the version history was not consulted. |
| H02 | Management's main levers for growth? | Supported | Declined | Vocabulary gap ("levers", "growing" vs "growth", "price increase"); keyword search without stemming or synonyms. |

### Actions (applied after run 1; re-measured on a new held-out set, not this one)

1. A figure answer must match the question's qualifiers (period, forward-looking, contracted, by segment); if not,
   decline as `no_evidence`. (H08)
2. Run the conflict check on every answer that touches a tagged metric, including passage-search answers. (H03, H04)
3. A single expert-call passage cannot answer a population question ("what share of customers"); decline or return it
   as a lead only. (H10)
4. Widen the change vocabulary (updated, latest, CIM) and use version history whenever a superseded value exists. (H06)
5. Test synonym expansion or embeddings for paraphrased questions (trade-off T2's trigger). (H02)

## After the fixes

All five actions were applied (`tests/test_run1_fixes.py` tests each with new phrasings). Re-running the run-1 questions
now gives 10/10 and the development set stays 30/30 – but the run-1 questions were used to find the causes, so this is
no longer a held-out result. **The published held-out result remains run 1: 4/10.** Run 2 uses new questions prepared
without access to the code, run once against the frozen build, with the commit recorded.

Stopgaps to note: the synonym list and the qualifier and population word lists are small and hand-written; they fix the
observed causes, not paraphrase in general. Embeddings remain the tested alternative (T2).

## Held-out run 2 (no-key mode)

Eight new questions, prepared by an AI assistant that had not inspected the implementation; the builder had not seen them. Run once on frozen build `197d4b1`.

| Measure | Result |
|---|---|
| Correct outcome | 6/8 |
| Citations resolving to a real, in-scope passage | 12/12 |
| Cited passages match the labelled support | 4/6 |
| Declined when it should | 1/2 |
| Answered when it should have declined | 1/2 |
| Conflicts shown | 1/2 |
| False conflicts | 1/6 |

### Issues (three questions)

| ID | Question (abridged) | Expected | Got | Cause |
|---|---|---|---|---|
| H2A-08 | Year-end net working capital? | Decline | Conflicted (NRR values) | **False conflict.** Generic words ("year", "end", "net") matched the cohort passage; the run-1 conflict check then attached that passage's NRR conflict to an unrelated question. |
| H2A-04 | Does retention clear 105% once the bundle is removed? | Conflicted | Declined | The question named the metric but also had enough other words to go to passage search; that search fell short of the match bar and the system declined instead of falling back to the figure and its conflict. |
| H2A-05 | How did the recurring-revenue mix move in the second CIM? | Changed | Changed, citation support failed | The "explanation" passage cited was about the revenue restatement, not the recurring-revenue share. |

### Fixes (applied after run 2; run 2 is diagnostic evidence only and is not re-scored)

1. A passage match must include at least one specific term; generic words alone cannot carry it. (H2A-08)
2. When a question names a metric and passage search falls short, answer from the tagged figures, with the conflict
   check. (H2A-04)
3. A version-change explanation is cited only if the passage is about the metric asked. (H2A-05)

Each fix is tested with new phrasings (`tests/test_run2_fixes.py`). Development set: 30/30; run-1 questions: 10/10
(development use). The post-run-2 results above are development checks, not held-out scores. Run 3 (below) is the next held-out check.

## Held-out run 3 (no-key mode)

Ten new questions drafted from the synthetic source documents without inspecting the implementation; the owner
reviewed the expected labels against those documents before the run. The questions were not used to tune the
implementation before the run; the fixes made afterwards were informed by its misses, so run 3 is not re-scored. Frozen at `beab828`; run once at `96a201b`, which differs only in
documentation and the wording of an output label. Results disclosed before any further change.

| Measure | Result |
|---|---|
| Correct outcome | 7/10 |
| Citations resolving to a real, in-scope passage | 11/11 |
| Cited passages match the labelled support | 2/6 |
| Expected values present | 1/6 |
| Declined when it should | 3/4 (all three for the right reason) |
| Declined when it should have answered | 2/6 |
| Conflicts shown | 2/2 |
| False conflicts | 1/8 |

### Per question

| ID | Expected | Got | Assessment |
|---|---|---|---|
| H3-01 tech remediation scale and spend | Supported | Declined | **Miss – paraphrase.** "Scale of work and spend … bring up to date" did not match "remediate", "months", "EUR"; the right passage was found but fell below the match bar. |
| H3-02 customer rights on change of ownership | Supported | Supported, **wrong answer** | **Miss – answered a different question.** "Biggest customer" matched the largest-customer-share figure; passage search fell short ("changes hands" vs "change of ownership"), and the run-2 fallback then answered with the 9% revenue share instead of the change-of-control clause. Counted correct on outcome only. A regression introduced by the run-2 fallback. |
| H3-03 retention after stripping the one-off sale | Conflicted | Conflicted | Correct outcome and citations; the answer omits the cohort's 111% including the bundle (in the cited passage, not in the answer text). |
| H3-04 keep the 80% recurring label? | Conflicted | Conflicted | Correct. |
| H3-05 why FY2025 sales fell in the restated IM | Changed | Declined | **Miss – vocabulary.** "Sales" is not recognised as revenue, so the version history was not consulted. |
| H3-06 adjusted EBITDA, first vs restated CIM | Changed | Changed | Correct outcome; citation support fails because the answer also cites the QoE's EUR 21.5m as a separate source conflict (a deliberate design choice the label did not include), and the EUR 2m / EUR 2.5m bridge figures appear only in the cited passages, not the answer text. |
| H3-07 recurring revenue excluding support as well | Declined | Conflicted (80% vs 71%) | **Miss – over-answer.** A hypothetical recalculation was answered with the existing conflict instead of a refusal. |
| H3-08 next year's sales tied to renewals | Declined | Declined | Correct (the run-1 qualifier fix held). |
| H3-09 120% from the US newsletter | Declined (wrong entity) | Declined (wrong entity) | Correct. |
| H3-10 Project Bramble figures | Declined (out of scope) | Declined (out of scope) | Correct. |

### What run 3 shows

- Four genuine misses (H3-01, H3-02, H3-05, H3-07); H3-02 is the most serious, a confident answer to a different
  question, and was caused by the run-2 fallback rule.
- The safety properties held for the third run: no invented or out-of-scope citations; wrong-entity and out-of-scope
  refusals correct; both conflicts shown.
- "Expected values present 1/6" mixes real misses with strict labels (bridge figures that appear only in cited
  passages). Answers that state derived figures in their own text would make this measure more useful.

### Fixes (applied after run 3; run 3 is not re-scored)

1. "Largest customer" alone no longer means the largest-customer revenue share; the figure is used only when the
   question asks for a share ("largest customer share", "largest customer accounts for"). (H3-02)
2. A hypothetical recalculation ("how much remains if …", "what would … be if …", "assuming …") is declined: the
   system does not recalculate figures on bases the documents do not give. A basis the documents state ("if we strip
   out the one-off bundle") is still answered. (H3-07)
3. "Sales" is read as revenue (a forward-looking "sales pipeline" is still declined by the qualifier rule). (H3-05)
4. A few more synonyms and filler words (biggest → largest, spend/cost → EUR, expect → estimate, code → codebase).
   A stopgap, not paraphrase handling in general. (H3-01)

Tests with new phrasings: `tests/test_run3_fixes.py`. A paraphrase such as "if the owner sells, can the top customer
walk away?" is now declined rather than answered with the wrong figure – a safe miss, not a solved one.

Development checks after the fixes (not held-out scores): development set 30/30; run-1, run-2 and run-3 questions all
answered with the correct outcome. Remaining label differences on run 3: H3-05 and H3-06 also cite the QoE as an
agreeing or separate source, and H3-03 does not repeat the cohort's 111% in its answer text.

Changing the metric vocabulary changed the memo's rendered evidence fingerprint, so the synthetic IC decision record was
re-confirmed against the new memo version; the metric vocabulary is now outside the evidence fingerprint.

## Model mode, first run (development set)

`gpt-5.4-mini-2026-03-17`, code `a7a01c8`, 25 model calls (out-of-scope questions are declined before any call),
estimated cost USD 0.023 against a USD 0.50 cap. Development set only – the rules were built on these questions.

| Measure | No-key mode | Model mode |
|---|---|---|
| Correct outcome | 30/30 | 28/30 |
| Citations resolving to a real, in-scope passage | all | 34/34 |
| Cited passages match the labelled support | 19/19 | 16/19 |
| Expected values present | 19/19 | 14/19 |
| Declined correctly (right reason) | 11/11 | 11/11 |
| Conflicts shown | 6/6 | 4/6 |
| False conflicts | 0/24 | 0/24 |

What it showed:

- The safety design held with a live model: every citation resolved, every refusal was correct, nothing invented.
- **The model flattened conflicts.** C01 ("What is net revenue retention?") came back SUPPORTED with one figure
  although live sources disagree, and one other conflict question was not shown as conflicted. The instructions
  forbid picking a value; the model did it anyway.
- It dropped figures and citations: C04 lost a citation; V03 and V04 omitted the QoE's separate figure; V02 lost the
  supporting citation and figures.
- M03's "values" miss is a scoring artifact: the model wrote "Netherlands", the label expects "NL".

Fix: the conflict check is deterministic and the model cannot override it. If the model answers as if sources agree
where the check found a conflict, the outcome is kept CONFLICTED and the missing conflict values are added with their
citations (`tests/test_llm.py::test_model_cannot_flatten_a_conflict`). Re-running model mode after this fix is a
development check. Product decision: no-key mode stays the default; model mode adds readable wording, not accuracy.

Development check after the guard (code `bef06f8`, USD 0.024, 25 calls): 29/30 outcomes, 6/6 conflicts shown, 34/34
citations resolved, 11/11 refusals correct. One outcome miss and some dropped figures remain – model wording, not
accuracy.

## Independent review before publication

A code reviewer (not the builder) checked commit `bef06f8` against the definition of done.

| Finding | Fix |
|---|---|
| G3 could be bypassed: a memo claim's `metrics` list narrowed which facts counted as dependencies, so a claim citing a passage with a conflicted fact could list another metric and escape the conflict check. | Every tagged fact in a cited passage now counts; the list cannot narrow it (`test_g3_cannot_be_bypassed_by_listing_a_different_metric`). More claims now show as depending on accepted conflicts (e.g. L02 on recurring revenue), which is correct. |
| The dashboard showed the development 30/30 without the held-out runs. | The dashboard now has an "Evaluation runs" table with every run, its authorship, code and result, reported separately (`data/eval/run_log.json`). |
| Clean-clone run not verified by the reviewer. | Run by the owner on a fresh clone; result recorded in the publication commit. |

The memo's dependency list changed, so the synthetic IC decision was re-recorded against the new memo version, as the
gate requires.
