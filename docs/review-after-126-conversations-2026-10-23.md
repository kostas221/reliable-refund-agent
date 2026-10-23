# Review after the 126-conversation run

23 October 2026. For the project owner and implementing engineer.

## Recommendation

Keep the existing financial safeguards and the completed code repairs. Fix the observed D37 offer recognition
defect, but do not turn a growing vocabulary list into the authority on consent. Replace implicit conversational
control with a small, persistent workflow for collecting an item selection and accepting an offered handoff.
Resolve selection before proposing, and distinguish asking for an answer from merely writing a question mark.

The two proposed patches address real problems. They do not cover seven of the nine clarification failures,
where no question was asked at all. The main next investment should be a mandatory selection step and a durable
wait for the customer's answer. Shipping intent, grounded citations and the D15 scenario contract also need work.
These are corrections within the existing v1.1 cycle, not a replacement product plan.

No business-policy relaxation, new framework, real payment integration or model upgrade is needed to address the
reproduced defects. The recommendations below have not been implemented. No paid request was made for this review.

## Evidence and limits

Code inspected: commit `f1a3eed`, with the latest results and documentation staged by the owner. Run:
`runs/pilot-20261022T165428Z-gpt-6-luna-none`, instructions v7, policy v2, configuration A.

The saved report gives 112/126 successful conversations (88.9%), 35/42 scenarios passing all three attempts,
27/27 required handoffs, 56/57 required citations and 0/126 observed unauthorized or duplicate refunds. Compared
with each scenario's preceding run, success is unchanged: paired difference 0.0 percentage points, reported 95%
interval -5.6 to +5.6. That comparison combines two earlier batches; it is not a concurrent randomized experiment.

I inspected all 14 machine-failed dialogue traces, D37 try 3, their relevant scenario contracts, the live prompt,
and the relevant graph, tool, read, domain and evaluator code. I counted all 706 agent responses in this run:
exactly three combine visible text with tool calls, all in D33. I did not independently repeat the claimed
historical scans of 1,566 messages and 3,946 responses, audit every successful conversation, or conduct a fresh
whole-application security audit.

| Main cause in the failed conversations | Cases | Count |
|---|---|---:|
| A proposal is created without first asking which item | D09 tries 1-2; D17 tries 1-2; D31 tries 1-3 | 7 |
| A question is emitted, but tools continue before its answer | D33 tries 1 and 3 | 2 |
| A shipping question is treated as a shipping refund request | D39 tries 2 and 3 | 2 |
| The historical refund answer omits the required `remaining` citation | D20 try 3 | 1 |
| The simulated customer accepts staff help, contradicting the fixed no-handoff expectation | D15 tries 2 and 3 | 2 |
| Total, assigning each conversation once | | 14 |

D37 try 3 passed the outcome checks after an unnecessary extra customer request. Repairing that defect improves
interaction quality; it cannot be counted as an additional success in this already-passed historical trial.

Free verification:

- Existing tests: 47 passed (`test_request_for_person.py`, `test_openai_adapter.py`, `test_agent_graph.py`).
- Review probes: 15 cases, 4 passed and 11 failed. Seven failures concern the current text detector, two exercise
  the current graph against PostgreSQL, and two concern a local sketch of the proposed question-mark predicate.
  The latter two are not failures of an implemented patch. These deliberately selected counterexamples are not
  an estimate of real-world error frequency or eleven independent root causes.
- The temporary reproducer is `.pytest_cache/review_20261023.py`; its cases are specified below for promotion into
  permanent tests with the corresponding implementation changes. It makes no model calls.

Earlier reviewed defects are materially repaired in this checkout: labelled model text is retained for replay,
all refusal reasons are considered, expired proposal replays expose the display status, and rejected proposal
replays include the staff reason. Do not discard these repairs because the aggregate success count is unchanged.

## 1. Review of the proposed offer patch

`refund_agent/refunds.py`, `_offers_person`, currently requires a person word and an offer verb in one sentence.
The D37 offer, "Would you like me to ask a staff member to help?", fails that predicate. Recognizing preference
questions and improving recovery is a justified immediate patch. "Has a staff member contacted you?" must remain
different from an offer, as the proposal correctly observes.

However, fixing only `_offers_person` leaves defects in `_asks_for_person`, `_accepts` and withdrawal handling:

| Input or exchange | Required result | Current result in the offline probe |
|---|---|---|
| "A staff member helped me yesterday. Where is my refund?" | No human request | Accepted as a human request |
| "The parcel is for my manager. Please refund the scarf." | No human request | Accepted |
| "A human is not needed. Please continue here." | No human request | Accepted |
| "Never mind the refund, I want to talk to a person." | Human request | Refused |
| Staff offer, then "Yes, please. My order has not arrived." | Accept the offer | Refused |
| "I cannot connect you with a staff member. Is the order number correct?", then "Yes." | No accepted offer | Accepted |
| D37's actual offer, then "Yes, please." | Accept the offer | Refused |

The first and second cases merely mention a person. The third negates the need after the person word. The fourth
and fifth negate a different subject. The sixth negates the offer itself. Adding `ask` or `would you like`
cannot fix those distinctions. Recognizing affirmative vocabulary is not the same as establishing what was
accepted. A statement such as "Would you like a refund? A staff member will review it" is another necessary
negative contrast: a person word and a preference question do not necessarily refer to the same action.

### Recommended implementation

When the system offers a handoff, record the offer explicitly: its ID, conversation, request revision, reason,
displayed question and message ID, and whether it is pending, accepted, declined or superseded. Use one clear
offer question, without combining it with an item choice or another yes/no question. The application should know
that it offered a person; it should not have to rediscover its own action by parsing its prose.

Resolve a reply against that offer. Keep ordinary affirmative/negative replies cheap, but distinguish an unknown
interpretation from an actual refusal. Scope negation to the handoff, not to every clause of the message. On an
uncertain interpretation, ask one focused confirmation instead of telling the customer that an ordinary yes is
invalid. Preserve the existing explicit handoff button as an unambiguous route. Do not require people who clearly
ask for staff in chat to learn a special phrase or press a button before being understood.

For a direct free-text request, use a separate, bounded intent decision with the latest customer message as
evidence. A structured label or exact quote is still a fallible interpretation, not proof of consent. Keep
contrasting examples and independent audit. If an additional model decision is needed, measure its cost and
errors; do not add an unbounded judge-and-retry loop to every message.

Keep the immediate offer patch independently tested, but treat it as a compatibility repair while this explicit
offer path is introduced. Log evidence type: customer button, interpreted direct request, accepted recorded
offer, or policy-required handoff. An agent's claim must not be described as a backend-proven semantic fact.

## 2. Review of the proposed question-and-tool patch

The D33 diagnosis is supported. In tries 1 and 3 the question accompanies `assess_refund`; the subsequent model
call proposes an item without a customer answer. Try 2 combines the question with `list_my_orders` and eventually
passes. Thus checking only writes on the same response would miss the actual failing path.

`Agent._route` currently routes any response with tool calls to `_tools`. The two database probes confirmed that
both "Which planter would you like refunded?" and "Please choose the planter from order d33-o1 or order d33-o2."
can be emitted alongside `propose_refund`, and a proposal is written before a reply.

The proposed `?` predicate catches the first case and misses the second. It also blocks a harmless lookup after
"You asked 'Where is my order?' I will check its status." A question mark can be quoted text; a request for input
can be an imperative. Conversely, `commentary` is a provider phase, not a reliable declaration that input is needed.

### Recommended implementation

Add an explicit, validated interaction action such as `ask_customer`, with a bounded reason (`item_selection`,
`handoff_acceptance`, or another supported clarification), a subject and any allowed choices. The action stores
a pending question and ends the turn. It is preferable to make this action mutually exclusive with effectful
actions. If a malformed model response nevertheless combines them, record each suppressed call with its original
call ID and an honest `not_executed / awaiting_customer` result, then end the turn without calling the model again.

An interim mixed-response guard can protect D33 while this is implemented, but the punctuation predicate should
be documented as a heuristic and tested for false stops. It cannot be the final workflow authority.

Persist the wait through restart. Resolve it only with an answer to that question from the appropriate actor:

- An unrelated customer message, a repeated receipt notice, or a staff approval does not select an item.
- An actual customer card action is a different, typed event bound to an exact proposal; it is not a generic
  answer to every outstanding question.
- A changed request invalidates the old selection and question revision. A handoff or cancellation must still
  be processed through its existing authorized path.
- Scope a wait to its request. A question about a future item must not corrupt a previously completed refund.

Pay particular attention to `Agent._run`, which currently resumes unfinished work before processing new input,
and to `notify`, which wakes the graph on staff decisions. Introducing a pause without adapting those paths can
replay a stale effect or clear the wait on the wrong event. Use the existing checkpoint mechanism; a simple
persisted wait ending at `END` is sufficient if implemented consistently. A native interrupt is an alternative,
not a requirement to rebuild the graph. Whichever is chosen, persist the pause and suppressed outputs before
resumption and test crash boundaries.

Changing the existing ordering test's text to a non-question is reasonable, provided its ordering assertions
remain. Add a separate test that forbids the old question-plus-proposal behavior. Renaming the old test alone
would hide the missing protection.

## 3. The main missing step: selection before eligibility and proposal

The seven no-question failures are not covered by either proposed fix. In the traces, a successful eligibility
assessment of arbitrarily chosen units is treated as sufficient reason to propose them. It proves that those
units may be refunded, not that the customer requested them.

Introduce a mandatory selection step before the first proposal or any replacement with different units:

1. Obtain relevant candidates from the signed-in customer's actual orders. Consider competing orders, variants
   and quantities. Do not infer the desired item solely from which unit is refundable or appears first.
2. Resolve the customer's reference to a set, retaining its supporting customer message and request revision.
   A unique description or explicit "both" can resolve it immediately; unrelated extra items should not cause
   unnecessary questions. When several sets fit, record unresolved selection and invoke the explicit question.
3. Keep the proposal tool unavailable while unresolved and enforce the same condition in its dispatcher/service
   path. Merely hiding a tool or trusting `resolved=true` from the model is insufficient.
4. Bind a resolved selection ID to the exact owned units and revision. The model can then propose that selection
   rather than choosing fresh unit IDs again. Reject stale, foreign or mismatched selections before any write.
5. Keep all existing financial, expiry, confirmation, staff approval, idempotency and handoff checks.

The detector that identifies ambiguity is still a language component. Evaluate candidate recall and selection
accuracy separately from enforcement. A gate cannot help if its detector silently misses a competing candidate.
Start with explicit references and stored choices; when meaning remains uncertain, ask instead of manufacturing
certainty. No production rule may consult scenario IDs, expected units, customer private facts or audit verdicts.

This makes D09/D17/D31 part of the same correction as D33. Reordering the prompt may be a later controlled
experiment, but it is no longer my recommended primary investment after repeated evidence of this workflow gap.

## 4. Shipping intent and policy interpretation

`check_handoff_reason` starts with `holds=True` and does not validate conversational evidence for
`shipping_refund`. A permanent test explicitly accepts that reason without a customer request. That is a known
trust boundary, and the D39 traces show its cost: the agent's incorrect interpretation ends the refund flow.

Distinguish three cases before applying the existing shipping policy:

| Customer meaning | Action |
|---|---|
| Wants to know whether shipping is included | Answer the shipping rule; continue the requested item refund |
| Requests that the shipping charge itself be refunded | Policy-required handoff |
| Meaning is genuinely unresolved | Give the policy fact and ask a focused clarification before handoff |

"Will shipping be refunded too, or just the kettle?" is the information case under the owner's recorded reading.
"Can you refund my shipping charge?" can be an action request despite being a grammatical question. Do not use
question marks, `can`, or a shipping keyword as the classifier. Require evidence tied to the current customer
message and a request-specific intent decision; quotes establish provenance, not meaning. Include negated,
hypothetical and historical shipping requests in the tests. A stronger handoff check must not make the other
reason codes an easy fallback for the same unsupported escalation.

No change to refund amounts, the thirty-day window, seventy-two-hour validity, original payment destination,
staff approvals or the named policy-required handoffs is justified by these results. Clarify the interaction
contract, rather than making more outcomes acceptable solely to raise the score. If policy prose changes, publish
a new version with its checksum and dated plan entry; do not overwrite frozen v2 or change historical scores.

## 5. Facts and citations should survive answer construction

D20 try 3 correctly gives the existing receipt and payout explanation, but omits `remaining`. The whole policy
was visible, so this is not simply retrieval failure. `reads._requests` also returns historical refund facts
without their directly applicable policy references.

Attach source references to the facts: this receipt, these already-refunded units, their once-only rule and,
when asked, the payout explanation. Preserve historical and current policy versions distinctly. For critical
facts, use a small response contract: subject, status, amount/receipt if applicable, and the rule being explained.
A short application-rendered sentence can supply a trusted fact and its citation; ordinary language remains
flexible around it. Check unsupported claims before publishing, not after the customer has seen them.

Do not append every citation to every message. The evaluator checks citation presence, so irrelevant citation
stuffing can improve its number without improving the answer. Keep human/semantic checks of relevance and
truthfulness. The earlier unsolicited test-ledger wording regression must remain a protected negative case.

## 6. Correct the evaluation contract separately

D15's role says to ask about the controller and then request the hair-dryer refund. It does not specify what to
do with an offered staff member, while its expected outcome forbids every handoff. In the failed traces the
customer explicitly accepts the offer and the agent honors it. Do not train the agent to ignore that request.

Version the simulator/scenario contract: for the intended two-topic refund case, specify that the customer
defers staff help and proceeds to the hair dryer. Preserve a contrasting case in which staff help is genuinely
accepted and handoff is correct. Do not silently turn these two historical failures into passes. Any comparison
using the revised contract must run both baseline and candidate under that same version, or explicitly report
the comparison only on the unchanged tasks until the new baseline exists.

Keep outcome and interaction quality separate. D37 passes today despite a false refusal and extra effort;
record false refusals, recovery turns and repeated questions as well as final success. The ambiguity pre-check
only verifies that some agent message and customer reply precede the proposal. Its subsequent dialogue audit
must still verify that the reply actually resolved the item choice. A blocked call alone does not prove a
correct clarification, and a model-written selection label must not become the grader's ground truth.

## 7. Verification and delivery order

Implement changes in small reviewable commits, but do not buy a complete live batch for every new phrase.

1. Turn the exact D37 and D33 traces into deterministic regressions. Add the contrary cases above. Keep the
   previous replay, authorization, transaction and notice-delivery tests green.
2. Implement the persistent question/offer state and selection enforcement. Exercise it with scripted model
   mistakes, including attempts to bypass the dispatcher and repeat suppressed calls after restart.
3. Implement the shipping intent distinction and grounded historical-refund response in separate changes. Check
   both their positive paths and protection cases; mark an integrated measurement as a package, not an isolated
   prompt experiment.
4. Resolve and version D15 before using it to claim improvement. Freeze candidate code, prompt, policy,
   simulator, evaluator and the comparison set before the paid comparison.
5. Before the owner starts a paid run: relevant tests, existing authorization/property/browser checks and the
   full mock flow; inspect one complete request; write predictions and a budget cap. Replaying old logs checks
   deterministic decisions, not what the model would say after a different tool result.
6. Run the predeclared complete evaluation and retain every attempt. Inspect every failure and newly recovered
   case; do not repeatedly rerun only failures until obtaining a clean number. Use replication for remaining
   uncertainty only after deterministic gaps are fixed. A fresh held-out set is the final generalization test.

### Required contrasts for the new workflow

| Family | Positive case | Negative/protection case |
|---|---|---|
| Item selection | Ambiguous item, then a real choice | Explicit both; unique order/date; no unnecessary question |
| Inventory variation | Same product in two orders | Reversed result order and renamed IDs must not change intent |
| Requested vs eligible | Customer names an unreceived item | Do not silently select a different, eligible item |
| Waiting | Question or imperative asking for input | Quoted question and normal read preamble do not create a wait |
| Answer matching | Reply selects one of the presented options | Thanks, silence, unrelated message and staff notice do not |
| Changed request | Customer changes the selected item | Old selection ID and old approval cannot authorize the change |
| Handoff | Direct request or accepted current offer | Historical mention, decline, unrelated negation, withdrawn offer |
| Shipping | Explicit charge refund request | Information question, hypothetical request, explicit exclusion |
| Crash recovery | Restart while waiting; retry after a completed write | No replay of a suppressed effect or duplicate question/output |
| Concurrent events | Relevant button/decision event handled once | Unrelated approval cannot answer a pending item selection |
| Claims | Actual proposal/receipt/rejection reason reported | No denial of a created proposal or payout claim without receipt |

Use stateful tests for sequences involving offer, reply, changed request, approval, cancel, restart and retries.
Add planted faults that remove the wait check, resolve it on any notice, accept a stale selection, or execute a
suppressed call. These tests should catch the defect deliberately, without depending on rare random draws.

For the next complete comparable run, track all four ambiguity scenarios (12 trials), the explicit-selection
contrasts (6 trials), all required handoffs (currently 27), required citations (currently 57), false handoffs and
false refusals, suppressed-call reasons, wrong-item proposals, unsupported action claims, cost and latency.
The desired result is correct behavior on both sides of each contrast, not merely more blocking. Report strict
success and pass^3 with denominators and task-level uncertainty. Do not translate 0 observed unsafe refunds into
a universal safety guarantee or promise 126/126 on unseen cases.

Configuration C needs an explicit comparison note: a new graph restriction changes which backend checks can be
reached. Keep A/C workflow conditions matched and document the intervention; do not attribute every improvement
to the original authorization checks.

## External practices that support this direction

- [Rasa flows](https://learning.rasa.com/rasa-pro/flows/) separates collecting a required value from executing an
  action. Its collection step waits until the value is supplied. Adapt that pattern to selection in the existing
  graph; this is not a recommendation to migrate to Rasa.
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) documents persisted pauses
  and explicit resume input. Nodes restart when resumed, so effects before a pause need idempotency or separation
  into their own node. This supports the restart tests and the warning about the current automatic resume path.
- [Fin Procedures](https://fin.ai/help/en/articles/13976254-building-fin-procedures) combines instructions with
  explicit steps and conditions, and recommends both trigger and non-trigger examples. Adopt paired intent
  cases and controlled transitions rather than copying another shop's business policy.
- [Fin escalation guidance](https://fin.ai/help/en/articles/13976161-manage-fin-ai-agent-s-escalation-guidance-and-rules)
  distinguishes offering escalation from escalating immediately, and cautions that broad escalation guidance
  increases handoffs. This supports recording an offer and honoring a meaningful response instead of treating
  every mention of staff as a request. Its default escalation rules are not this project's policy.
- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) recommends moving
  known arguments into application code and using object structure to avoid invalid combinations. A proposal
  bound to an already resolved selection follows that principle. Tool outputs must remain linked to their call IDs.
- [Anthropic's agent evaluation guidance](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)
  distinguishes capability tests from regression tests, and discusses ambiguous tasks and grader limitations.
  Apply that distinction to the D15 contract and the protected successful paths; combine state checks with
  calibrated dialogue review rather than optimizing only a displayed pass count.

These sources describe engineering practices, not evidence that any vendor would outperform this project on
these 42 scenarios. The concrete workflow above is a proposed adaptation. The measured evidence in this review
is the saved run and the stated free tests, not an unperformed live experiment.

## Scope of this review's changes

Only this review document and disposable review probes were added. Application code, policy, prompts, scenarios,
saved results, the frozen plan and the owner's staging were left unchanged. No full suite, paid model call,
commit or push was performed.
