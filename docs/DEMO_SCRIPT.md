# 90-second demo script

Open the dashboard (`docs/index.html`) or run the commands. Say the label first.

**0–10 s – label.** "This is a personal prototype on synthetic data with illustrative criteria. It isn't based on any
firm's systems. It prepares evidence; people make the decisions."

**10–25 s – screening evidence.** `python -m dealintel screen D-LARK --as-of 2026-05-12`
"On the first memorandum, Larkspur meets four criteria with a cited value each, and two are unknown. Unknown is an
outcome, not a guess, so they become diligence questions. A deal-team lead recorded the decision to advance."

**25–45 s – a source conflict.** `python -m dealintel ask D-LARK "What is net revenue retention?"`
"Two months later the answer is conflicted: management says 112%, our cohort analysis says 104% once a one-off bundle
sale is removed. The system shows both with their passages and doesn't pick one. The conflict stays visible; the deal team records 104%
as the working case with a rationale. 104% is below the 105% criterion, so this matters for IC."

**45–65 s – effect on the memo gate.** `python -m dealintel memo D-OSIER` then `python -m dealintel memo D-LARK`
"On Osier, a memo claim relies on an unresolved retention conflict, one claim has no citation, a red flag has no owner
and the drafter reviewed their own memo, so the gate blocks it with four reasons. On Larkspur, the VP accepted each
conflict with a base case and a rationale. The conflicts stay visible in the memo, every red flag has an owner and a
treatment, an expert-call rumour is labelled an unverified lead, and the gate passes."

**65–85 s – the human decision.** (dashboard step 5)
"The IC chair recorded PROCEED with three conditions, tied to this exact memo version. If anyone edits the memo, the
decision shows as stale until the IC re-confirms."

**85–90 s – close.** "30/30 on my own questions; on held-out questions I had not seen, 4/10, then 6/8, then 7/10 on
human-drafted questions – reported separately, with every miss and its cause in the findings."
