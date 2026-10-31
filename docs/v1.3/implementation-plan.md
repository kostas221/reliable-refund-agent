# Reliable Refund Agent v1.3 implementation sequence

Created: 2026-10-30. Revised: 2026-10-31 after the owner's review.

Status: recommended narrow repair sequence. The original proposal was larger than the observed failures
justified. This revision follows the existing scope and stopping rules in [plan.md](../plan.md), records the
corrected H255 diagnosis, and defers the larger interaction changes with activation conditions.

## Recommendation

Close the v1.2 evidence, respect the separately registered reasoning-effort experiment, make two bounded product
repairs, measure the final combination once, and finish Phase 7. The two repairs are:

1. Give the agent trustworthy deadline information in order reads and correct misleading arrival advice.
2. Extend the existing selection check to the ambiguity exposed by H281, with tests for additional false refusals.

Expected benefits are hypotheses until measured. No new interaction subsystem or commercial platform is needed
for this repair sequence.

## Current evidence

The held-out and stress reports now exist, and Claude has read all 243 conversations. The held-out report records
A at 50/57 conversations and 16/19 scenarios successful in all three tries; B at 54/57; C at 49/57. A's success
interval is 71.9% to 100.0%. Stress is 23/24 in each configuration, with one invalid simulation per configuration.
These are the saved reader's judgments, not a completed owner-validated narrative report. The latest plan entry
still records the owner's review and final narrative as outstanding.

Sources: [held-out report](../../runs/final-v1.2-20261030T170445Z/report.md),
[stress report](../../runs/stress-v1.2-20261030T174734Z/report.md), [plan change log](../plan.md).

The 19 held-out and 8 stress cases have been copied into development as D63-D89 with provenance. Their original
files and results remain frozen. New runs on those copies are development evidence, not a new unseen evaluation.

## Step 0 Close v1.2 and keep the registered experiment separate

Finish the owner's independent reading and the final v1.2 narrative under the existing protocol. Preserve misses,
simulator faults, denominators, uncertainty and the model-selection rule.

The owner has separately registered a comparison of Luna reasoning `none`, `low` and `medium` on D63-D89, with
three attempts per scenario, an unchanged product, and its own predictions, budget caps and decision rule. Follow
that registration in [pilot predictions](../pilot/predictions.md). Do not mix the deadline or selection repairs
into that experiment. The owner runs any paid commands.

More reasoning may change whether the agent calls an assessment or asks a clarifying question. It does not itself
supply the missing scenario time. Choose the setting by the registered rule and keep it fixed when measuring the
two repairs, so their effect is not conflated with a model-setting change.

## Repair 1 Deadline information and valid next-step advice

### Corrected diagnosis

In H255, none of the nine A/B/C conversations called `assess_refund`; they answered from `list_my_orders`.
The list exposed the delivery date but no deadline or current scenario time. The agent therefore lacked the
trusted information needed to determine that the window had elapsed. A said that arrival later would allow a
refund in 3/3 tries. The window was omitted in all 9/9 tries of this one scenario; these are repeated attempts,
not nine independent business situations.

A separate defect exists in `_named_case`: even when assessment returns both missing-return and deadline blockers,
its generic next-step text says the item must arrive first. Fixing that text alone cannot change an answer in
which the tool was never called.

Sources: [H255 transcripts](../../runs/final-v1.2-20261030T170445Z/A/transcripts.md),
[order reads](../../refund_agent/reads.py), [agent tools](../../refund_agent/agent/tools.py).

### Change

- Expose the refund deadline and whether the ordinary window has elapsed in the order data the agent actually
  reads. Calculate these from the existing policy function and scenario/application clock, using one evaluation
  time for the response. Do not ask the model to do calendar arithmetic or duplicate the number of days.
- Distinguish a time fact from full eligibility. An elapsed ordinary window is not an unconditional refusal:
  earlier on-time proposals and other named policy cases still use the existing assessment and domain checks.
  Missing or implausible delivery times must not be presented as a known valid or expired deadline.
- Correct arrival guidance so that it never presents receiving the item as sufficient while another blocker
  remains. Preserve truthful partial explanations and the policy's named disputed-return cases.
- Supply the relevant policy reference beside the new facts. Keep confirmation, staff approval, amounts and
  transaction checks under their existing rules.

Use `assess_refund` when the full item-specific decision is needed. The narrow repair does not introduce a new
mandatory call before every answer or a second policy engine.

### Acceptance checks

Add tests that fail on the old payload/advice and pass after repair. Cover an expired window plus a missing
return, a timely missing return, the exact deadline and just after it, an earlier on-time proposal, mixed item
history, and missing/implausible delivery dates. Confirm that read-only enrichment creates no proposal or payment.

The free saved-trace review verifies that H255's actual read path now supplies the missing fact and that tool
advice is consistent with all blockers. It does not prove that a model will use the new fact; the live confirmation
measurement checks that separately.

## Repair 2 Extend the existing item-selection check

### Diagnosis

H281's black camera wrist strap and black camera pouch have different names before the first comma. The existing
check groups only identical pre-comma product families, so it does not examine their ambiguity. A proposed both
in 3/3 attempts despite recognizing that the customer might mean either. The customer later corrected the
proposal; this finding did not establish a wrong committed payment.

The selection check already runs inside the proposal transaction. A limited extension is the first repair to
measure before introducing persisted choices and UI controls.

Sources: [selection.py](../../refund_agent/selection.py), [refund service](../../refund_agent/refunds.py),
[H281 transcripts](../../runs/final-v1.2-20261030T170445Z/A/transcripts.md).

### Change and acceptance checks

Define a general, bounded extension based on the existing product data and customer's request, not a special case
for the scenario ID or camera products. Extend both candidate grouping and the distinguishing information the
check recognizes: changing grouping alone may still reject a clear answer when neither product name has a comma.

The tests must demonstrate:

- An ambiguous request does not permit a proposal for one guessed item or both items.
- A clear request for the strap, the pouch, or explicitly both permits exactly that selection.
- Mentioning an item, excluding it, or changing one's mind is distinguished from selecting it.
- Unrelated products sharing a color or common word do not cause unnecessary refusals.
- Existing same-order/cross-order variants and identical units continue to work.
- A refused attempt does not replace or otherwise mutate an existing open proposal.

Report the method as a bounded language check with measured limits, not a general guarantee of understanding.
If it cannot meet these contrasting cases with a small coherent change, record that negative result rather than
adding an indefinite list of phrase exceptions.

## Validation and stopping rule

For each repair, run the failing reproduction and contrasting cases, then a mocked end-to-end recovery path.
Replay the saved relevant calls for free and report separately which old wrong attempts would be blocked and
which previously correct attempts would newly be blocked. Replaying old calls cannot establish the model's
response to a new tool result or refusal.

Once both repairs are complete, run the required full free checks and authorization/integrity checks. Keep the
simulator, grading rules and customer roles fixed while comparing the product changes. The implementing agent
runs free checks; the owner runs any paid model call in Git Bash.

Prepare one development confirmation measurement on the agreed development set, using the selected reasoning
setting. Before it runs: record the question, predictions, acceptance criteria and enforced budget cap; run mock
end to end and inspect one complete logged prompt. Publish targeted outcomes, new false refusals, overall success,
process faults, simulator fidelity, latency and cost, each with its denominator and limits.

A critical safety defect or a correctness regression caused by the repairs reopens the necessary bounded repair.
An ineffective change is reported and either reverted with the final combination measured, or released with the
unmet criterion explicitly stated. Other weaknesses remain recorded for later. Do not continue tuning until every
known example passes. This development run is not a new held-out claim.

Implemented changes receive dated entries in the original plan's change log. Commits and pushes require the
owner's instruction. This document does not allocate or execute additional paid runs beyond the owner's decisions.

## Deferred work and activation conditions

| Work | Evidence currently available | Condition to reconsider |
|---|---|---|
| Persisted item picker and button lifecycle | H281 and known limitations of word-based selection | Ambiguous selections still escape the narrow repair, or false refusals and repeated clarification materially obstruct valid requests in the confirmation measurement or human trial. |
| Recorded alternative/staff offers | Premature cards in 12/186 development conversations and the D40 pronoun-related refusal | The same problem recurs in distinct situations, or human trial feedback establishes a meaningful usability obstruction. A safety defect takes immediate priority. |
| Multiple-request tracking and sequential simulator confirmations | D15 and the known single-confirmation coverage limit | Repeated loss of supported requests or an established need for those interactions justifies the bounded workflow and coverage extension. Until then, disclose the coverage limit. |
| Broader requirement to assess every item-specific answer | H255 currently identifies a missing-information path | Misleading eligibility advice persists after the relevant facts and corrected guidance are supplied, and measurement supports a stronger enforced assessment path. |

The triggers do not require a wrong payment before usability can matter. They also do not authorize a new business
flow without applying the scope rule.

## Phase 7 Complete the project

After the bounded repair and confirmation cycle, complete or verify each existing packaging deliverable: README
quickstart and honest results/limits, reproducible Docker and mock setup, required CI checks, license and data
provenance, the short demo video, and the planned qualitative trial with five people using their own English.
Record their difficulties and recovery without reporting a population success percentage from that small sample.

Rasa, Shopify, Gorgias and Fin remain design references. Their larger workflow features, commercial refund rules,
new fees, real payment integration and fine-tuning are not selected work for this release.
