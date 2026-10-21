# Findings

## Held-out evaluation, run 1 (no-key mode)

Ten questions written by a reviewer who had not seen the rules, phrased the way a deal team would ask. Expected
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
no longer a held-out result. **The published held-out result remains run 1: 4/10.** Run 2 uses new questions written by
someone who has not seen the code, run once against the frozen build, with the commit recorded.

Stopgaps to note: the synonym list and the qualifier and population word lists are small and hand-written; they fix the
observed causes, not paraphrase in general. Embeddings remain the tested alternative (T2).
