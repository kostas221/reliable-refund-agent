# Review after the selection check: what to improve next

For the implementer and project owner. Read-only review of commit `a8b5869` and the available artifacts of
`runs/pilot-20261023T144102Z-gpt-6-luna-none`, inspected on 2026-10-23. This is an evidence update within the existing
v1.1 cycle, not a replacement for the frozen plan or a completed dialogue audit.

## Recommendation

Keep the measured clarification improvement. Repair the remaining selection-check counterexamples, address the
shipping-question and citation failures, and settle the D15 simulator contract. Then compare Luna `none` with Sol
`low` on the same fixed implementation. A stronger model is a useful candidate; it does not establish that a
check which accepts an explicit rejection is correct.

Do not change the refund window, approval requirements, amounts, original-payment rule, or idempotency to improve
the score. The observed failures do not justify changing those business rules.

## What is actually available

At inspection, the new folder contains **125 result files out of 126 planned**. `D42/try3/result.json` is absent.
The audit file has **125 entries, all `read = false`**. The missing artifact does not establish why that try is
missing, whether it ran, or what its result was.

- 119/125 have no machine-detected failure (95.2%); their stored verdict is `unknown`, not `passed`.
- Six conversations have machine failures, detailed below.
- No saved result reports a system error, simulator error, budget stop, unauthorized refund, or duplicate refund.
- All 12 ambiguity-order pre-checks clear. Reading the customer/agent exchanges confirms that D09, D17, D31 and
  D33 ask which item and receive a distinguishing answer before the proposal. Previously only 3/12 cleared.
- D32 and D34 still propose without an unnecessary clarification in all six tries.
- Nine proposal attempts were refused by `units_named`, in nine conversations. Each was followed by a
  clarifying exchange; none of these conversations has repeated selection refusals.
- 54/56 required citation checks pass among the available results.

These are development cases already used for tuning. This review read the six failing transcripts, the twelve
clarification exchanges, and the explicit-choice, accepted-handoff, and shipping-request controls. It did not
independently audit every conversation or certify generalization to new cases. Complete the artifacts and audit
before reporting a final success rate or paired improvement interval.

## The six remaining observed failures

| Case | Tries | Observation | Recommended correction |
|---|---|---|---|
| D39: shipping information | 1, 2, 3 | The agent treats "Will the shipping I paid be refunded too, or just the kettle?" as a shipping-refund request, hands off, and never refunds the kettle. | Make information, an action request, and unresolved intent distinct. Answer the policy question; require evidence of a shipping-refund request before that handoff. |
| D20: an existing refund | 1, 2 | Correct receipt and payout information, but no `remaining` policy citation. | Return the applicable `remaining` citation next to already-refunded units and the receipt, and require the relevant explanation when using that fact. |
| D15: shipment then refund | 2 | The customer explicitly accepts staff help for the shipment. The agent correctly hands off, but the fixed expected outcome requires a later hair-dryer refund and forbids handoff. | Version the simulator/scenario contract to define whether the customer defers the offered help and continues to the refund, or accepts help and ends in handoff. |

For D39, `check_handoff_reason` still has no branch requiring request evidence for `shipping_refund`; this reason
falls through with `holds = True`. A non-empty quotation alone would prove that words occurred, not what they
mean. Use a clearly resolved request; if uncertain, ask a narrow question before changing conversation control.
Do not classify by a question mark: "Can you refund my shipping?" can be a real request. Preserve D40's genuine
shipping-refund handoff, which works in all three available tries.

For D20, the full policy and the instruction to cite `remaining` are already present. The proposed change places
the source beside the relevant fact rather than merely repeating a longer prompt. Do not add unrelated citations
or remove the criterion to obtain a passing score.

For D15, keep the historical failure under its original contract. Re-run both compared configurations under the
same revised contract, or report the changed scenario separately. Do not teach the agent to disregard a real
customer request for a person to satisfy the old oracle.

## Reproduced gaps in the new selection check

The current check is a useful ambiguity brake, but its positive result is not proof of the customer's current
selection. I called the production `look_alikes_unnamed` function through the existing `tests/test_selection.py`
fixtures; the following five counterexamples all return that the proposed selection is allowed:

| Customer context | Proposed selection that the check allows | Why it should not be accepted as resolved |
|---|---|---|
| "Not the olive one. Please refund the rust one." | Olive scarf | A negated mention counts as positive evidence. |
| Earlier: "Please refund the olive scarf." Later: "Actually, keep the olive one. Refund only the rust scarf." | Olive scarf | Old and current words are pooled without invalidating the old choice. |
| "I sent the scarf back two weeks ago. Please refund it." | Both scarves | The unrelated word `two` satisfies the all-items expression. |
| Agent: "Do you mean the olive one?" Customer: "No." | Olive scarf | The fallback tests what the agent's question named, without checking the answer. |
| Same question; customer: "Thanks." | Olive scarf | Acknowledgement is treated as a resolving answer. |

The positive control, "Please refund only the olive scarf", correctly allows the olive scarf. These are five
targeted counterexamples, not a random error-rate estimate. They exercise selection validation only; they do not
demonstrate an unauthorized payment. Customer confirmation and staff approval still protect execution.

Relevant code: `refund_agent/selection.py`, `_ALL_OF_THEM` (line 33), `_picked` (line 109), the concatenated customer
history (line 133), and the question fallback (line 144). `refunds.propose` uses this function inside its transaction.

Required behavior before trusting this guard on new scenarios:

1. A negative or unresolved reply must not resolve an item question. Distinguish yes, no, and unresolved for the
   active question, retaining which item or choices it referred to.
2. A changed or withdrawn selection must invalidate earlier supporting words. Keep the current request's selected
   units and supporting message, rather than treating every mention in the conversation as current consent.
3. Quantity and all-items expressions must refer to the requested items. Time expressions or quantities of other
   products must not select this group.
4. Negation must apply to the item it excludes. If meaning is not resolved safely, ask; matching a variant word
   alone must not be presented as proof of selection.

Add regression cases for these inputs and their positive opposites, plus an acceptance test proving that a refused
selection writes no proposal and does not supersede the existing one. If these cannot be represented reliably in
the small existing check, revisit the already-proposed explicit selection state. Do not assume that an LLM-produced
`resolved = true` would itself prove correctness.

Two additional declared limits remain: product families depend on the catalog's naming convention before a comma,
and the person-request tests retain three expected failures for mentions of people that are not requests for a
handoff. Exercise those with contrasting development cases before claiming robustness to unseen wording. An
explicit family/variant field is preferable if the catalog is expanded; a whole catalog migration is not required
just to test another model.

## Model comparison after the focused corrections

Sol `low` is the most direct next candidate: the adapter and pricing path already support it. The old v1 comparison
was Luna `none` 41/60 versus Sol `low` 50/60. That is evidence for testing the configuration, not a forecast for this
new implementation, and it changes both model and reasoning setting.

Use the same code, policy, tool definitions, scenarios, simulator, approval script and grading rules for both
configurations. Hold the model and all these settings fixed within each run. Register the question, predictions,
budget and criteria first; verify with free mock tests and one complete logged request before the user makes paid
calls. If the task budget permits, Luna `low` is a separate diagnostic to distinguish an effort change from a
model change; it is not required to decide between the two product configurations.

Measure full task success, success in all three tries, unnecessary and missed handoffs, clarification on ambiguous
and explicit requests, incorrect proposal attempts, recovery after refusal, latency and cost per correctly resolved
case. Include currently passing scenarios, not only the six failures. The current run can serve as a baseline only
for its exact implementation and scenario contract; code or simulator corrections require a matching baseline.

After choosing the configuration on development data, freeze it and evaluate on genuinely new scenarios. Do not
keep adjusting the implementation against that new final set. This follows the official recommendation to compare
models on the same inputs and choose the lightest configuration that meets the quality requirement:
[OpenAI model selection](https://developers.openai.com/api/docs/guides/model-selection).

## Verification performed for this review

- Existing focused tests: **62 passed, 3 xfailed**, in 1.92 seconds, covering selection and requests for a person.
  The three expected failures are declared limitations, not successful protections.
- Five additional pure-function selection counterexamples reproduced; one positive control behaved correctly.
- Available run results counted directly and the relevant transcripts read as described above.
- No paid calls, database mutation tests, full-suite rerun, production-code changes, policy changes, audit edits,
  historical-result edits, staging, or commit. This report is the only added project file.
