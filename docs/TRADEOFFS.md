# Product trade-off record

Each entry: the options, the decision, why, what would change it, and when to revisit. Prototype context: synthetic data,
illustrative policies.

## T1. A small, traceable workflow in v1 – not live sourcing or CRM integration

- **Options:** (a) broad platform – sourcing feeds, CRM, relationship mapping, portfolio monitoring; (b) one workflow
  from screening to an evidence-backed IC memo, done end to end.
- **Decision:** (b).
- **Why:** the costliest failure in a deal process is an IC discussion built on a figure nobody can trace, or on a
  conflict nobody noticed. Trust in the evidence trail is the condition for adoption of anything else; a broad platform
  with weak traceability would lose the deal team's trust in the first IC. Sourcing and CRM also need live data and
  integrations that a prototype cannot show honestly.
- **Would change it:** pilot evidence that the memo workflow is trusted and used (memos through the gate, citation
  support above an agreed bar), or a clear deal-team pain in sourcing that outranks diligence.
- **Revisit:** after the first pilot cycle (next).

## T2. Keyword and metadata search before embeddings

- **Options:** embeddings / vector search; keyword (BM25) with deal and version filters.
- **Decision:** keyword search, scoped to the deal's live documents, with figure questions answered from tagged facts.
- **Why:** deal vocabulary is specific (NRR, QoE, change of control) and keyword results are explainable; scope filters
  remove the most damaging errors (another company's numbers, a replaced version). It also keeps the default mode
  reproducible and free.
- **Would change it:** the evaluation showing paraphrased questions failing to retrieve the right passage.
- **Revisit:** when a held-out question set exists.

## T3. No-key mode as the default; model mode optional

- **Options:** model-first answers; deterministic answers with an optional model to phrase them.
- **Decision:** deterministic by default; model mode phrases answers from a fixed evidence pack, with citation
  validation and a per-run cost cap.
- **Why:** reproducible results, tests that never call an API, and a baseline to compare the model against on the same
  evaluation set. The model adds readability, not authority.
- **Would change it:** model mode beating the baseline on citation support and refusal with acceptable cost.
- **Revisit:** after each model-mode evaluation run.

## T4. Conflicts are shown and decided by people, never auto-resolved

- **Options:** pick the most recent or most authoritative source automatically; show all values and record a decision.
- **Decision:** show all values; a named person accepts a base case with a rationale; the conflict stays visible in the
  memo ("accepted – sources still disagree").
- **Why:** which basis to use (management vs adviser definitions) is a judgement the IC needs to see, not a data
  cleaning step.
- **Would change it:** nothing in v1; precedence rules could pre-fill a suggestion later, still decided by a person.

## T5. The gate blocks the memo; it does not block the IC

- **Options:** block any IC decision on a non-ready memo; allow DECLINE or REQUEST MORE WORK on any memo, PROCEED only on
  a READY one.
- **Decision:** the second.
- **Why:** the IC must always be able to stop or redirect a deal; only a decision to proceed needs complete evidence.

## Arbitrating competing requests

Priority order when needs collide: (1) IC evidence standards – citations, conflicts, owners – are not traded away;
(2) deal-team speed in diligence; (3) operating-team requests (value-creation tracking, 100-day plans) go to *next*.

Worked example: the deal team asks for one-click export of the memo to the IC deck before the gate passes, to save time
before an IC meeting. The operating team asks for red flags to flow into a 100-day plan tracker. Decision: export ships,
but only of a gate-passed memo, with the fingerprint on every page (speed without weakening the evidence standard);
the 100-day plan feed goes to *next*, because it adds a new user group before the core workflow has proved adoption.

## Roadmap

| Phase | Scope | User problem it addresses |
|---|---|---|
| Now (v1, this prototype) | Screening with evidence, cited Q&A, conflicts and versions, memo gate, recorded IC decision | "I can't trace this number" / "we missed that two reports disagree" |
| Next | Extraction from real documents with human confirmation, held-out evaluation, access control, export of gated memos, red flags into the 100-day plan | Manual fact tagging; IC-pack preparation time; hand-off to the operating team |
| Later | Sourcing signals and CRM, comparables from licensed data, portfolio monitoring against the IC case | Finding and prioritising targets; checking the investment case after closing |
