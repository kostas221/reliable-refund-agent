# Remaining gaps after the step 2 repairs

22 October 2026. For the project owner and implementing engineer. This review updates the next actions after
`docs/next-improvements-2026-10-21.md`, section 7, was implemented. It proposes corrections and experiments for the
existing v1.1 cycle, not a new product plan. No policy relaxation or financial authorization change is proposed.

## Recommendation

Retain the successful repairs. Complete the approved contrasting development cases and one controlled instruction
ordering experiment. Prepare two concrete tool-message corrections identified below. For the remaining behavior
failures, prioritize an explicit item-selection step and answers grounded in backend facts and applicable policy
sections, rather than a succession of broader instructions. Keep simulation validity separate from agent quality.

90/90 is a useful development aspiration, not a result we can promise. A clean batch on known cases would still
need replication and the new independent held-out evaluation. Do not add scenario-specific production rules,
weaken the grader, or rerun only failed conversations to obtain that number.

## What was inspected and verified

Baseline: `runs/pilot-20261021T224855Z-gpt-6-luna-none`, implementation `5ef910f`, result commit `f2765e7`, agent
instructions v7, policy v2. The current report records 81/90 strict success, 24/30 pass^3, 18/18 required handoffs,
24/27 required citations in D11-D30, and no unauthorized or duplicate refund in 90 trials. The protected set is
67/69. The saved audit is Claude's; the owner's review is pending. The reported 81/88 valid-simulation view depends
on two simulator-fault judgments discussed below.

The change from 79/90 is +2.2 percentage points, with a paired 95% interval of -5.6 to +11.1. This small batch does
not establish improvement over the immediately preceding candidate. The repairs do have concrete supporting
observations: the required handoff recovered, and unsolicited test-ledger explanations fell from 35/90 to 0/90.

Review work included all nine machine-failed traces, the corresponding scenario instructions, the successful
D13/D15 contrasts, prompt v7, policy v2, graph/tool/read/domain code, simulator and relevant evaluation paths.
Two small offline reproductions exercised the real policy evaluator/result conversion and tool wrappers with
stubbed domain calls. They made no database changes or provider calls. Findings below distinguish those results
from untested live-model effects. This was not a fresh audit of all ninety successful/failed dialogues or the
entire application's security.

## The nine unresolved conversations

| Cases | Count | Observed problem | Correction to investigate |
|---|---:|---|---|
| D09 try 3; D17 tries 1-3 | 4 | A proposal precedes the required item clarification. D09 proposes both shirts; D17 selects one of two orders. | Separate selection from eligibility; enforce the selected conversation stage before proposing. |
| D12 try 2 | 1 | The correct amount is explained but its `amount` citation is omitted, although two tool results supplied it. | Preserve the source of the amount explanation through answer construction. |
| D20 tries 2-3 | 2 | A historical refund and receipt are reported with `payout`, but without `remaining`. | Give historical-refund facts their applicable policy reference and preserve it in the answer. |
| D13 try 3; D15 try 1 | 2 | The customer asks for a person and the agent correctly hands off, contrary to the scenario's forbidden-handoff expectation. | Review the simulator/scenario contract before assigning a cause or changing agent behavior. |

D17 try 1 also falsely denies having created a proposal. It is already one of the four clarification failures,
not a tenth failed conversation. Its confirmation and payment were authorized by the existing buttons; the
failure is premature selection and misleading communication, not an observed authorization bypass.

## 1. Item selection needs a controlled step

`refund_agent/agent/graph.py` stores messages and usage, then allows the model to choose tools from the same set
on each turn. It has no explicit record that item selection is unresolved. `_tools` executes the requested call
through domain checks; those checks establish ownership and refund validity, not what an ambiguous phrase means.

In D17 all three attempts select the compact shears, which appear first in the returned order list. The hidden
customer preference happens to match that choice, so the buttons approve it. That is not evidence the agent
understood the choice. A list-position preference is a hypothesis worth testing, not a demonstrated cause.

The approved policy-first/behavior-last experiment remains a reasonable next measurement. Keep it bounded: one
predeclared candidate, with the proposal-boundary reminder, unchanged policy content and a complete protection
check. Do not describe ordering plus a reminder as the isolated effect of ordering.

If it still fails, implement selection within the existing graph:

1. Load the customer's candidate items across relevant orders. Read-only assessment remains available, but an
   eligible assessment is not evidence that the customer selected those items.
2. Record a selected set with its supporting customer message, or record that several interpretations remain.
   An explicit "both" is a valid set; an exact item/order reference can resolve selection without another question.
3. While selection is unresolved, ask a focused question and wait for a customer answer. Do not make
   `propose_refund` available in that stage, and also reject a premature call in the tool dispatcher. Hiding a tool
   alone is not enforcement. Check state before each effectful call, including a batch or resumed run.
4. Bind selection to the request's revision and conversation. A changed request invalidates it; an unrelated
   customer message or an approval notice does not resolve it. Persist this state through restart.
5. Pass exact units to the existing proposal service, which retains all current financial checks and approvals.

Selection interpretation is still a language task. A model-written `resolved=true` or an exact quote by itself
does not prove meaning. The selection step must consider competing candidates and be evaluated separately;
the guard enforces the recorded decision, not perfect language understanding. Do not implement keyword matching
for just "shirt" and "shears", or require clarification for every order containing multiple items.

Test both the detection and the guard: same-order variants, different orders, explicit requests for both, unique
references, reversed list order, changed preference, and a restart while waiting. Keep internal fixture IDs and
expected units out of agent-visible selection logic. Disclose any graph restriction that changes reachability in
configuration C; it must not be silently counted as an original backend-check effect in the A/C comparison.

## 2. Make policy sources and action status part of answer construction

The two citation problems have different mechanisms. D20 reads historical requests from `reads.orders`, which
does not attach their policy references. D12 already receives `refund-policy/v2/amount` twice, yet replaces it in
the response with `approval`. Merely returning another citation cannot guarantee that either is communicated.

First attach applicable, versioned references to the relevant facts: a paid unit's receipt and once-only rule;
the eligible amount calculation; and the applicable refusal reason. Use the loaded policy and backend facts,
not `scenario.expected.cites`. Keep facts about different requests and policy versions distinct.

For the response, introduce a small contract for critical content: the selected request/items, current status,
amount/receipt when applicable, and the policy reasons actually being explained. Validate these against trusted
results before publishing the message. A fixed, concise sentence can render a known fact with its reference,
while ordinary conversation remains natural. For example, an amount explanation can state the paid amount and
cite `amount`; a historical-refund explanation can name the receipt, say the units cannot be refunded again and
cite `remaining`. A timing explanation adds `payout` only when relevant.

Implement this as a separately measured candidate if sources beside facts and the bounded prompt experiment do
not suffice. Do not append every policy citation to every reply: the current evaluator checks occurrence, which
could be satisfied without actually supporting the answer. Review relevance and entailment as well as presence.
The application must not import scenario expectations or evaluator helpers to decide what to say.

The same response contract should prevent contradictory essential status statements. Render known action status
from the backend rather than letting the model invent whether a proposal exists. Validate before `_mirror`
publishes user-facing text: correcting it after storage/display is too late. Retain original model output in the
trace and the delivered message separately, so intervention is auditable. Give any model-based repair a strict
attempt/cost bound; avoid an extra judge call on every routine reply. A fixed fact sentence does not by itself
make unrestricted accompanying prose truthful, so that limitation must remain in the dialogue audit.

## 3. Two additional tool-message defects reproduced offline

These are gaps in the current code, not established causes of the nine observed failures. Correct them with
regression tests rather than waiting for a new scenario to expose them. Keep each patch separate from the prompt
ordering candidate; if changes run together, label the result as a package comparison.

### A. A second refusal reason loses the return-dispute guidance

Both `assess_refund` and `propose_refund` select `_NAMED_CASES` using only `reasons[0]` in
`refund_agent/agent/tools.py`. The pure policy evaluator for a delivered order forty days old, with an unreceived,
unrefunded unit, returns `('window', 'return')`. Feeding that real decision into the assessment wrapper produces
only "Tell the customer why ... Propose nothing"; `return_disputed` is absent.

Policy v2's `return` and `exceptions` sections still name a case for a person when the customer says those units
were sent, even when a different rule refuses payment. A plain deadline-exception request remains a refusal.

Correct recovery using all relevant reasons and unit-specific facts. Do not simply hand off every multi-reason
refusal or every missing return. Preserve the existing `check_handoff_reason` validation and the distinction
between "already sent" and "will send later". Test lateness plus a missing return, lateness alone, mixed returned
and unreturned units, and already-refunded units. The offline result proves missing guidance, not that a live
model will necessarily omit the handoff; the full policy is also in its context.

### B. An idempotent proposal replay gives stale confirmation instructions

`refunds.propose` returns `_result(existing)` for an existing request key. `_result` preserves the current status
but returns outcome `eligible` for non-ineligible statuses. The tool's next-step text is selected by outcome alone.

The offline reproduction exercised that real result conversion and tool wrapper for six statuses:

| Returned status | Current next-step text | Correct communication |
|---|---|---|
| awaiting_customer_confirmation | Waiting for the customer's button | Appropriate while still valid |
| awaiting_staff_approval | Waiting for the customer's button | Confirmation exists; waiting for staff |
| approved | Waiting for the customer's button | Approved; existing execution prerequisites apply |
| cancelled | Waiting for the customer's button | Closed; do not ask to confirm it |
| refunded | Waiting for the customer's button | Already paid; use its existing receipt |
| expired | Waiting for the customer's button | Expired; not actionable |

Generate the next step from current status and validity, keeping original policy outcome distinct from lifecycle
state. Use existing display-status logic where applicable, including time expiry before a stored status has been
updated. Preserve request identity and idempotency; do not create a replacement merely because a replay sees a
closed request. Add database-backed tests for create -> confirm/cancel/pay -> repeat the original call ID, checking
both the message and unchanged proposal/operation counts. The reproduction stubbed the domain call; it did not
exercise a database restart. Existing financial checks still prevent an invalid confirmation or payment.

## 4. The two simulator flags need a clearer scenario contract

Do not treat 81/88 as an independently established score until the flags are reviewed. The saved strict result
remains 81/90 whatever that review decides.

In D13, the customer's goal says "whole bedding order", while the behavior accepts a refund for the two returned
items and says the blanket will be sent later. There is no explicit stopping instruction specific to that
partial resolution. Asking how to return the blanket is plausible under the broader goal. The general simulator
prompt says to end when the goal is reached, but these instructions leave room for different readings.

In D15, the behavior says to ask about the controller and then the hair dryer. In the flagged trace the customer
does ask for the hair dryer, but also accepts the offered staff help. The instructions do not explicitly say to
decline or defer that offer, even though the expected handoff is forbidden. This is at least specification
ambiguity, not clear evidence of an agent defect or an unambiguous violation by the simulator.

For future versions, state the simulated person's intended choices in the customer role, without exposing the
grader: whether to defer staff help, and whether the future return is outside this conversation's goal. Retain
contrasting cases where the customer really does want a person or return instructions, and honor those requests.
Do not force every customer to accept an answer or stop as soon as money is recorded. Keep adaptive language and
paraphrases; use scripted traces only as supplemental regression tests, not as a replacement for conversational
evaluation.

Version changed scenario/simulator instructions and rerun baseline and candidate under the same version. Preserve
the old outputs and flags with a review note; do not relabel these two trials as passes or silently remove them.
Make the review identify the exact role instruction allegedly violated, and permit uncertainty. Model-based
audit judgments need human checks, particularly for these disputed cases.

## Delivery and measurement order

1. Keep the current candidate and all saved results intact. Write the contrasting cases and the assertions for
   the two reproduced tool defects before changing behavior. The existing twelve-case plan should cover the
   selection contrasts; add the combined-reason and replay cases to free contract tests, not an endless paid set.
2. Complete the already approved instruction ordering experiment once, with fixed comparison conditions. Prepare
   the two tool-message fixes independently; do not mix them into a run described as ordering-only.
3. If clarification remains unreliable, promote the explicit selection workflow to the next candidate. Measure
   correct questions and unnecessary questions separately. Do not keep appending the same instruction.
4. Address citation propagation and, if needed, the response contract in a distinct candidate. Protect the wording
   and required handoffs repaired in the current run. Review the simulator specification in its own versioned
   comparison; simulator changes cannot be credited as agent improvements.

For every candidate: relevant free checks, mock end-to-end and complete request inspection first; predictions,
scope and runner cap before the user starts paid calls. Require no observed unauthorized/duplicate refunds,
18/18 required handoffs, no unsupported customer-request handoffs, and no false action-status claims. Target
all six clarification trials and all 27 required citations, while reviewing every failure among the previously
protected 69 trials. These are screening targets, not statistical guarantees.

Run complete predeclared comparisons and retain every attempt. Report strict success, simulator validity,
pass^3, costs, and paired uncertainty; group related new variants by family. A repaired past trace is not a
prediction of how many successes the next stochastic batch will gain. Freeze candidate, policy, simulator and
grading before the next independent held-out set. The historical twenty held-out cases used for tuning are spent.

## External practices used in this recommendation

- [Fin Procedures](https://fin.ai/help/en/articles/13976254-building-fin-procedures) documents explicit steps,
  conditions and positive/negative triggers. The adaptation here is a bounded item-selection stage, not copying
  another shop's refund or escalation policy.
- [LangChain guardrails](https://docs.langchain.com/oss/python/langchain/guardrails) describes checks around model
  and tool calls, and distinguishes predictable rule checks from fallible, more expensive semantic checks. The
  proposed response and tool-stage checks can use the existing graph; no framework migration is required.
- [Anthropic agent evaluations](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) recommends
  unambiguous tasks, balanced cases, trace inspection and checks against evaluator loopholes. This supports
  reviewing the simulator flags and citation meaning rather than optimizing only the displayed pass count.

These are documented engineering practices, not evidence that a vendor would score better on these cases or
that the proposed changes guarantee 90/90. Only this review document was added. Application code, policy, tests,
scenarios, audits and saved scores were not changed. No paid call or full suite was run for this review.
