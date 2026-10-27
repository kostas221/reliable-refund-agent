# Review of v1.2 fixes 1-6 and the proposed measurement sequence

Review started 2026-10-26; checked again and completed 2026-10-27. This review uses the current uncommitted
implementation and the owner's supplied A-D sequence.
It supersedes the current-state recommendations of `review-generalization-2026-10-26.md`, whose counts described
an earlier snapshot. It does not change the frozen plan, implementation, scenarios or audit verdicts.

## Recommendation

Keep the six fixes and finish their stated validation. Before a paid development run, repair the remaining
definitive language-grading error, close the simulator's last-message gap, and specify how changes to the grader
and simulator will be distinguished from improvements to the product. A general rewrite or more agents is not
justified by the evidence reviewed here.

Fixes 2 and 3 address real workflow/information gaps. Fixes 4 and 6 now attach policy context to backend results;
they already implement much of the direction suggested by the earlier review. Prompt v9 should align with these
tool changes. Writing four small prompt edits is reasonable, but their size alone does not demonstrate transfer to
new cases.

## Updated measurement status

The Claude audit now marks all 180/180 dialogues read. Applying the saved audit and the explicitly dated evaluator
correction with `evaluation.audit.apply` gives:

| Configuration | Strict successes / scheduled | Successful in all three trials | Simulator-invalid trials |
|---|---:|---:|---:|
| A, Luna with full checks | 40/60 (66.7%) | 11/20 (55%) | 1/60 |
| B, Sol with full checks | 51/60 (85%) | 17/20 (85%) | 0/60 |
| C, Luna with lab checks | 38/60 (63.3%) | 9/20 (45%) | 1/60 |

These are the saved model reader's judgments plus mechanical checks, not a completed owner-validated final report.
The raw results remain A 39/60, B 45/60, C 39/60 without mechanical failures; they are not the same measurement.
Both views must remain visible with the reason for the difference.

Under the current audited view, B minus A is +18.3 percentage points; the existing paired bootstrap by scenario
gives a 95% interval of +6.7 to +33.3 points (20 scenarios, three trials each, 10,000 draws). This is provisional
on owner review, but it no longer supports the earlier suggestion that the new evaluation shows no model
difference. The interval captures scenario-sampling uncertainty conditional on the current judgments; it does not
include uncertainty in the reader or the corrected grader. Sol reaches both numerical quality targets in this
view; Luna does not. Preserve the existing model
selection order: first qualify on safety and quality, then compare cost per resolved case. A cheap Luna development
run can still test repairs, but it should not predetermine the eventual model choice.

The saved financial checks are unchanged: 180/180 expected financial outcomes passed, with 81 committed demo
refund operations and zero detected unauthorized or duplicate refunds. These are finite synthetic/test-ledger
results, with repeated scenarios, not a guarantee for production or a real payment provider.

## Confirmed implementation findings

### 1. The revised clarification check can still definitively fail a valid conversation

Locations: `refund_agent/evaluation/evaluator.py:357`, `:362`, `:428`.

`asks_which` recognizes any question with `which`, `do you mean` or `or just` as a product-selection question. Free
helper checks reproduced all three false positives:

- `Would you like a short explanation, or just the proposal?`
- `Which part of the payment policy would you like me to explain?`
- `Do you mean you already sent the parcel?`

A minimal in-memory trace with exact items already named, the first question answered, and a subsequent proposal
returns a failed `proposes_without_asking` pre-check. The dialogue audit cannot overturn a mechanical failure.
This repeats the original failure mode with a narrower word rule.

Recommended correction: retain definitive mechanical failure when no required proposal exists, but route uncertain
language classifications to pending reader judgment. Word matching can flag a conversation; it should not decide
the meaning irreversibly. Add these counterexamples without growing an exception list for every phrase. These are
selected failing examples, not a live estimate of the classifier's error rate.

### 2. The simulator retry can miss a question followed by a fact line

Location: `refund_agent/evaluation/customers.py:94`; message forwarding: `evaluation/runner.py:186`.

The retry looks only for `?` in the last transcript entry. The runner forwards an agent's answer and an appended
fact line as separate messages. Therefore an actual question can be followed by a policy fact line without a
question mark, and the protection does not run. A fake model returning `[END]` reproduced one call for that shape
versus two calls when the question alone is the last entry. An imperative such as `Please tell me whether you want
a staff member to review the shipping charge.` also receives no retry.

Recommended correction: inspect the whole last agent turn, not merely its last message. Keep questions without
punctuation within the fidelity audit unless explicit pending-question state is introduced. Do not treat punctuation
as proof that another customer response is mandatory: an optional closing offer may legitimately be declined by
ending the conversation.

### 3. Count simulator interventions explicitly

The second call is correctly logged and budgeted through the same recording adapter. No missing-cost defect was
found. However, a second `[END]` becomes the same `customer_ended` outcome as a normal ending, and the report lacks
dedicated counts for reminder attempted, reply obtained, and unresolved ending.

Record those separately and flag unresolved cases for audit. The historical 23/1,604 conversations ending after a
question is a diagnostic count, not a validated prediction that v2 will need intervention in exactly 1.4% of future
conversations. A change to the simulator is a change to the measurement conditions, even when it fixes a real flaw.

## Corrections to the proposed A-D sequence

### A. Finish and validate the current repair bundle

Retain the proposed mutation checks, replay and full suite. Add the confirmed counterexamples above. For fixes 4
and 6, verify that every emitted policy fact is true for the particular request and items, relevant to the answer,
and valid at the observed state. A source ID merely appearing somewhere in the dialogue is not sufficient evidence
that the corresponding explanation is correct. Include mixed-item and unrelated historical-proposal negatives;
do not broaden citations by listing every policy section.

Replay can establish what a renderer or guard would do on saved inputs. It cannot establish how the model will
respond to new tool outputs, a decline notice, or the changed simulator. Reserve those claims for the live
development measurement.

### B. Freeze the grading rule before new scenario authoring

Changing the citation criterion may be justified as a product decision, but keeping the number 85% does not keep
the same target if fewer conditions can fail. Show the v1.1 strict score alongside the v1.2 definition, and rescore
the old saved dialogues under both definitions where the existing evidence permits it. This is free and reveals
how much apparent improvement comes solely from changing the rubric.

Recommended rule: citations are required for a material policy decision or a policy explanation the customer needs,
including an eligible decision when its reason matters to the request. Their absence from incidental factual
updates can be a separate quality measure. Do not define the rule only as refusal/handoff/question: that could
exclude the justification for a successful but conditional refund. For each mandatory source, the author must
state the customer-facing obligation it supports. The author cannot require an arbitrary policy section merely
because it exists in the fixture.

The package v2 should explicitly distinguish legitimate interpretation of the customer's request, a required
clarification, asking permission to start after answering a question, and an actual unnecessary product-selection
question. Its examples must include acceptable alternative wording and paths, not only a reference dialogue.

### C. Avoid an open-ended repair loop on the 62 development scenarios

Moving the used 20 scenarios into development is correct. Keep their original files, freeze record, raw results and
provenance; create development copies. The 62 scenarios are now regression and tuning material, not proof of
generalization.

Replace "if any new category appears, fix it and continue" with a written stopping rule: one full confirmation run
after the current repairs; any safety defect, or a correctness regression caused by this bundle, reopens the
necessary repair. Other weaknesses are reported and prioritized against the stated completion criteria, rather
than silently extending the loop until all known cases pass. Any reopened cycle has a named question and a bounded
check before another paid run. This rule never permits leaving a known critical safety defect unresolved.

Compare before/after product versions under the same simulator, grading rule and fixture semantics on any paired
live comparison. Fix 6 also changes how past `invalidated` proposals are seeded: the reason becomes
`order_or_policy_changed`. That may correctly express the intended new fixture, but it must be recorded as a
fixture interpretation change rather than attributed entirely to agent quality.
If the only old evidence uses simulator v1 and the new run uses v2, label it a combined system/measurement change;
do not attribute the whole difference to the six product fixes. The A/B/C comparison inside the final batch remains
valid for its stated question when all three use the same frozen simulator.

### D. Define what the 40 new scenarios represent

Freeze the implementation and rubric first, then author, validate and freeze the new set before running it. Use
fresh, independently authored cases with no leaked traces or expectations. Independence of authoring does not
require excluding every familiar business rule: the product has a finite refund policy. Avoid near-duplicate
templates across tuning and test sets, while keeping ordinary supported flows represented. Report deliberately
novel or difficult combinations separately. This is designed coverage, not a measured real-customer distribution.
Fix the group definitions, counts and their contribution to the overall score before authoring, and report every
group regardless of its result.

Forty scenarios reduce some sampling uncertainty; they do not prove general reliability. With 40 scenarios and
three attempts, the thresholds become 102/120 successful conversations and 28/40 successful in all three. A/B/C
would produce 360 conversations. Keep zero observed **unauthorized and duplicate** effects as requirements for the
full-check configurations A and B, alongside the unchanged financial and ownership invariants. C remains the
isolated experiment with explicitly relaxed checks.

The supplied sentence "new errors in the 40 are what step C tests" is incorrect. C tests known development cases;
D tests transfer to fresh cases. Fixes informed by D require a later version and new evidence. Publish D even if
the targets are missed, as already proposed.

## Owner review and close-out details

The suggested 30 owner-read dialogues do not match the currently recorded sampling rule. Calling the existing
`review_sample` on this run now selects 70 flagged/corrected/noted dialogues plus 11 sampled from the rest: 81 total.
The frozen predictions refer to this rule. If a smaller owner review is chosen, record it as a protocol deviation,
report its coverage and selection, and do not describe it as full compliance with the original protocol. In
particular, preserve owner review of post-run corrected verdicts and a non-cherry-picked sample of apparent successes.

The cost figures in the supplied sequence are estimates, not enforced caps. Bind the actual approved cap in the
runner, including simulator reminders, retries and failed trials. No paid call or commit was made during this
review; the owner remains responsible for paid commands. The existing uncommitted implementation was not changed.

## External support and limits

[Anthropic's evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) supports
separating regression from capability tests, reading trajectories and checking that graders do not reject valid
solutions. [Fin's procedure documentation](https://fin.ai/help/en/articles/13976254-building-fin-procedures)
documents explicit steps, conditional paths and simulations. These support the direction of the existing repairs
and the review recommendations; they do not validate our specific implementation or promise a success rate.
