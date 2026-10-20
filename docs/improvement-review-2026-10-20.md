# Improvement review after the v1 evaluation

20 October 2026. For the project owner and the engineer implementing the next version.

## Recommendation

Start v1.1 by making the policy, backend assessments and conversation controls agree. First give the agent the
whole small policy, then provide a read-only refund assessment with authoritative reasons, and resolve the policy's
handoff ambiguities in a new version. Measure these changes before selecting a stronger model.

The evidence supports these priorities; it does not establish a future success rate. The v1 result and frozen
files remain historical evidence. This document proposes changes and verification; it does not implement them or
change v1 scores, rules, prompts or scenarios. Implementation should have the dated entry required by the plan.

For the policy v2 handoff, also read [the final consistency check](#final-consistency-check-of-the-policy-v2-table).
It incorporates the owner's ten-row draft, resolves overlapping rules and lists the acceptance cases needed
before the next evaluation. The short table in section 3 must be read with those precedence and lifecycle rules.

## Evidence checked

Reviewed the current tools, graph, policy search, eligibility functions, domain services, read projections,
simulator instructions and evaluation/reporting code alongside `docs/final/results.md`. Recomputed outcomes from
all 180 saved results and their current audits in `runs/final-20261019T201207Z`, inspected selected raw failures,
and reproduced the policy search and zero-paid-unit behavior without calling a model.

The base commit was `cb8500e`, with uncommitted reporting/audit/documentation changes. This review preserves that
work. The baseline is the published final evaluation, not a claim about an untested implementation.

| Configuration | Successful conversations | Scenarios successful in all three tries |
|---|---:|---:|
| A, Luna, all backend checks | 41/60 | 11/20 |
| B, Sol, all backend checks | 50/60 | 15/20 |
| C, Luna, selected execution checks disabled | 40/60 | 10/20 |

No unauthorized or duplicate committed refund was observed in these 180 conversations. C did not exercise the
missing checks through attempted unapproved payments; this is not evidence that the checks are unnecessary.

The current policy, rendered with section IDs, is 12 sections, 712 whitespace-separated words and 4,216
characters. Required-citation availability was independently counted from saved tool results:

| Required section | A | B | C |
|---|---:|---:|---:|
| Shown and cited | 17 | 20 | 19 |
| Shown but not cited | 2 | 0 | 3 |
| Never shown, but cited | 0 | 0 | 0 |
| Never shown and not cited | 8 | 7 | 5 |

Thus 56/61 shown required sections were cited, compared with 0/20 unshown ones. This is an association in saved
traces, not a controlled estimate of the gain from adding context. Eight A conversations missed an unseen
required source; one also had another failure. Fixing the seven citation-only failures, with everything else
unchanged, would yield 48/60, still below the 51/60 target. That arithmetic is an opportunity estimate, not a
forecast of the changed agent.

Seventy-two existing tests passed: `test_agent_tools_shape.py`, `test_eligibility.py`, `test_amounts.py` and
`test_report.py`. No paid request was made. The full suite and browser tests were not rerun because no application
code was changed.

## 1. Give the agent the full policy and attach applicable citations to tool results

**Current code:** `refund_agent/agent/policy_search.py:50`, `refund_agent/agent/tools.py:140`,
`refund_agent/agent/tools.py:148`, `refund_agent/agent/graph.py:87`.

`WordSearch` returns three sections based on word overlap. A correct answer depends on whether the model happens
to ask a query that matches the policy's wording. This affects the stronger model too.

Replaying the actual A H04.try1 query locally:

```text
When does a card refund reach the customer's card after the refund is processed? Timing for card refund settlement.
Returned: validity, scope, approval
Required: payout
```

The existing search tests cover eight familiar questions and one harder query; their passing does not establish
coverage of natural customer wording. In A H02.try3, the eligible proposal returned `policy_citations: []`, leaving
the agent to explain the discounted amount without the corresponding section.

**Change:** assemble a trusted policy context by iterating `Policy.sections`, calling `Policy.rendered_text(section.id)`
and `Policy.citation(section.id)` before the first agent call. Include every section and its versioned ID. Generate it from the controlled policy source;
do not maintain a second prose copy in the prompt. Keep customer/seller text outside the trusted policy block.
Return applicable citations with eligibility, amount and previous-refund information, including successful
proposals. A receipt remains the only evidence of execution.

A new retrieval service is not needed for the current 712-word corpus. If it grows, measure retrieval coverage and
end-to-end resolution before choosing a more complex retriever. Exposing a source does not ensure the agent will
apply or cite it correctly; those remain evaluation questions.

**Verify:** the first request contains all current IDs and policy text; no stale version is mixed in; natural
phrases about timing, discounts and prior refunds receive supported explanations. Check citation relevance,
not just whether a final answer includes a list of every section.

## 2. Assess refunds without creating proposals

**Current code:** `refund_agent/eligibility.py:123`, `refund_agent/refunds.py`, `propose`, and
`refund_agent/agent/tools.py`, `propose_refund`.

The backend already computes eligibility, but the agent generally obtains that decision by creating a proposal.
It can instead improvise a reason from order data, as A H09 did, or create an unwanted proposal while answering a
follow-up. Telling the model to create a proposal before every refusal would also turn informational questions
into writes. A H03.try3 created another proposal after the customer merely said they would return the remaining
blanket later.

**Change:** add a read-only domain assessment for exact requested units, using the same policy functions and
trusted-data loading as proposal creation. Since the full policy is available, this can replace the search tool
in the next version's offered tool set rather than adding another overlapping tool. For example:

```json
{
  "outcome": "refused",
  "primary_reason": "order_not_delivered",
  "reasons": ["order_not_delivered", "return_not_received"],
  "amount_minor": null,
  "policy_citations": ["refund-policy/v2/eligible-orders", "refund-policy/v2/return"],
  "explanation": "This order is still in transit. It is not eligible for a refund through this flow.",
  "assessed_at": "...",
  "order_version": 1
}
```

This is a proposed schema, not an existing endpoint. Keep reason codes distinct from policy section IDs. Define
which reason takes precedence when several apply. Return an amount only where a financial refund is eligible;
an assessment is neither approval nor a reservation. Load ownership and facts inside the service, and recheck
them at proposal creation and execution to handle state changes after the assessment.

Customer claims may justify a staff check under policy, but cannot set trusted return-received data. Support
partial eligibility explicitly, explaining excluded units and obtaining agreement for the proposed subset.
The independent evaluator must retain its own authored expectations rather than importing this service as its
oracle.

**Verify:** assessment does not insert/invalidate proposals or move money; it rejects foreign IDs; assessment and
proposal decisions agree on the same snapshot; changes after assessment are caught before payment. Test mixed
eligibility and the precedence of order status over a secondary missing-return explanation.

## 3. Write policy v2 with explicit handoff rules

**Current code:** `policies/refund-policy-v1.toml`, sections `exceptions`, `payment`, `return` and `payout`;
`refund_agent/eligibility.py:136`; `refund_agent/refunds.py`, `hand_off`.

The policy sends every exception request to staff, while several scenario expectations prohibit handoff after
the agent refuses an impermissible subrequest. Its payment wording also leaves a cancelled original card open
to interpretation. Changing only the prompt leaves these competing instructions in place.

Create a new policy version and agree the business choices before writing its new evaluation expectations:

| Situation | Recommended behavior for this demo |
|---|---|
| Customer clearly requests a person | Honor the request; close pending proposals safely |
| Trusted facts meet a named manual-review condition | Explain it and hand off |
| Customer requests more than the paid amount or a different refund destination | Refuse that subrequest with its reason; offer the eligible refund and obtain exact confirmation, unless a separate mandatory handoff condition applies |
| Customer accepts the allowed amount | Before payment, continue the card-confirmation and staff-approval flow; after a committed receipt, acknowledge without a new proposal or handoff |
| Customer says an unreceived item will be sent later | Explain the prerequisite; no new refund for that item or automatic handoff; preserve an existing eligible request for other items |
| Customer says it was already sent, but trusted records show no receipt | No payment; staff checks the discrepancy under the existing return policy |
| Customer requests an exception to a hard rule | Refuse the override; preserve named manual-review routes, including qualifying earlier on-time requests, and honor an explicit request for a person |
| Customer asks for shipping charges back | Hand off for review under the named shipping rule; the automated ledger cannot refund shipping and staff approval does not bypass that restriction |
| Customer reports a delivery that never arrived | Hand off to investigate the reported discrepancy; the claim alone does not authorize payment |
| Original card is cancelled, but the test payment remains valid | Explain the demo's original-payment rule, refuse a new destination, and continue if the customer accepts; do not guarantee an issuer's eventual processing |
| Customer asks when a committed refund reaches their bank | The demo receipt proves a simulated ledger operation, not a real bank transfer; promise no arrival date |
| Order is still in transit and the customer asks about cancellation | Explain that cancellation is outside this refund flow; offer staff contact, and hand off when requested |
| Selected unit has no paid amount | Explain that it has no money to refund; offer only the other eligible positive-value units, with exclusions disclosed and exact card confirmation |

Define precedence explicitly when refusal and manual-review conditions coexist, using the final consistency
check below. An unsupported payment request
does not make the original payment record invalid. Explicit requests for human help must still be honored.
The recommendations above resolve demo policy choices; they are not a declaration of any real shop's obligations.

There is relevant provider precedent: Stripe documents refunds to the original payment method and explains that
the card issuer handles expired/cancelled-card refunds, which can still fail. That supports clarifying H14's
ambiguity, but does not make this simulated ledger a payment-provider integration. See [Stripe refund
destinations](https://docs.stripe.com/refunds#refund-destinations).

Keep the existing numeric limits, ownership checks, exact confirmation/approval binding, original destination,
transactional checks and deduplication. The observed failures do not justify loosening those controls. Update
policy version/hash, generated documentation, routing rules and new-version expectations together; retain v1.

## 4. Make conversation progress explicit, especially clarification and completion

**Current code:** `refund_agent/agent/graph.py:42`, `refund_agent/agent/tools.py:94` and `:202`.

The graph currently remembers messages and usage; the model chooses each next action. Examples of the resulting
drift:

- A H07.try1 recognized two possible pruning-shear orders but proposed one without asking which the customer meant.
- A H02.try3 handed off with `decision_needed: "None."` after the customer confirmed the completed refund was correct.
- A H03.try3 handed off while saying there was no current decision for staff.

**Change:** record current intent, candidate units, selection evidence, pending proposal and whether the requested
work is complete. Let the model interpret language and ask useful questions, while code validates IDs and the
actions available in the current business state. Use a bounded structured reason for an agent-initiated handoff,
with the triggering condition or customer message recorded for audit. Reject unsupported automatic handoffs;
offer the customer a choice when the need is unclear. Keep the direct customer handoff path available.

An LLM-produced `customer_asked` flag or confidence score is not independent proof of a request. Natural-language
intent still needs interpretation; a stored flag alone cannot guarantee correct understanding. Reuse explicit UI
item selections when available, and ask when competing interpretations remain.

Do not force clarification just because multiple units exist: “refund all three” is different from an unspecified
“the shears.” After completion, “thanks,” “that is the correct amount,” and “I will return the other item later”
should not initiate another financial request or a handoff. A genuinely new request must still work.

**Verify:** ambiguous item across two orders, explicit item ID, multiple identical units, whole-order request,
changed selection, cancelled request, acceptance after receipt, and a new request after completion. Include
positive tests where a person is required so that reducing unnecessary handoffs does not suppress necessary ones.

## 5. Ground explanations in backend facts and tighten semantic grading

Use backend reason codes with structured parameters: delivery time, deadline, assessed time, paid amount,
remaining units and receipt. Render critical facts from those fields, allowing conversational wording around them.
Check receipt/amount/section references before displaying final claims; validate amounts semantically, including
whole currency amounts without decimal digits.

A committed receipt retrieved through an authorized status read also proves a previous simulated refund.
The current `prompts/agent-v3.md` instruction mentions only a receipt returned by `execute_refund`; replace that
wording in the new prompt so that reporting an existing refund never requires another execution attempt.

A concrete audit concern is A H11.try3. The saved response says the decision is based on the purchase date; the
actual rule starts at delivery. The v1 review accepted this as a minor wording error. This review recommends
flagging it for adjudication and explicitly rejecting a wrong deadline anchor in future tests. The backend's
decision was correct; the customer-facing explanation was not. This document does not silently rescore v1.

Also distinguish causes in A H09.try3: after an incorrect initial explanation, the customer explicitly asked for
a staff member. That final handoff follows the real request, even though the scenario forbids handoff. The earlier
wrong reason still fails. Trace analysis should not teach the next agent to ignore an actual request for a person
merely to satisfy a static scenario label. Conditional simulator behavior and goal changes need explicit rules.

Report safety, monetary outcome, explanation accuracy, citation support and routing separately, alongside strict
overall success. Extra diagnostics explain failures; they do not replace the existing strict score or excuse
unsafe actions. Use small human-labelled examples to calibrate graders for each criterion. Preserve original
judgments and evaluator versions when a grading defect is corrected.

## 6. Fix the zero-paid-unit inconsistency before adding broader scenarios

**Current code:** `refund_agent/scenarios.py`, `Unit` permits `paid_minor >= 0`;
`refund_agent/eligibility.py:168` sums selected paid amounts;
`refund_agent/refunds.py:921` requires every execution line and the total to be strictly positive.

For a delivered, on-time order with a valid payment, returned free gift and returned paid item, the pure policy
currently gives:

```text
requested ('free-gift',): eligible, amount 0, no reasons
requested ('free-gift', 'paid-item'): eligible, amount 10000, no reasons
```

Both selections contain a zero-paid line and conflict with execution's positive-line requirement. This is a code
consistency defect exposed by a new synthetic example, not an observed failure in the 180 final conversations.
The pure policy was executed; a complete database workflow for this example was not run in this review.

Define zero-paid handling before a proposal is confirmable. A zero-only request should receive a clear no-money-
to-refund explanation. A mixed request must not block the paid units or silently misrepresent the selected set;
explicitly distinguish returned units from financial refund lines. Keep financial ledger lines positive and
test zero-only, mixed free/paid and an ordinary positive refund through the whole lifecycle.

## 7. Select the model after improving the surrounding system

B's 50/60 versus A's 41/60 is real evidence in favor of the stronger agent on this set. Its recorded agent cost
per resolved case was about $0.01032 versus $0.00062, a factor of 16.6. These are this run's costs, not a new price
quotation, and exclude staff work. Both models repeatedly missed the same policy information.

First compare the improved context/tools using the cheaper agent. Then compare Luna and Sol under the same new
policy, tools, simulator, limits and grading. Choose by resolution, consistency, staff workload, latency and
absolute cost. If a later routing experiment is warranted, use observable difficulty signals and a bounded
fallback before committing actions; do not trust a model's self-reported confidence as a safety gate.

## 8. Improve the test distribution and isolate each intervention

The development set did not expose the citation-retrieval weakness: its required citations were supplied by the
backend in refusals/referrals. New development coverage should test informational questions and allowed refunds
as thoroughly as denials. Keep successful straightforward cases to detect regressions too.

1. Preserve the v1 run, original held-out files and freeze manifest. Use versioned development copies of the used
   scenarios for diagnosis; do not erase their original provenance.
2. Measure a context-only intervention under policy v1, then backend assessment/explanation changes under the same
   rules. Do not attribute a gain to context when the policy, model and grader changed simultaneously.
3. Develop policy v2 and its matched expectations as a separate business-specification change. Compare model
   candidates under that one fixed specification. A score under new rules is not a clean software-only improvement
   over the old benchmark.
4. Add controlled regression variants: paraphrases, reordered items, changed amounts, precise time boundaries,
   alternative interpretations, additional benign follow-ups, and paired required/forbidden handoffs. Swapping
   order ownership must change access; renaming a product must not change numeric eligibility.
5. Review scenario instructions, private facts, scripted button actions and expected outcomes for agreement before
   running. Separate a simulator deviation from an agent error, retaining any safety failure regardless.
6. Write and freeze 20 genuinely new held-out cases for the final v1.1 claim, with new combinations and situations,
   not just renamed copies of these failures. Choose the final candidate and targets before running them.
7. Before each paid development batch: run free regressions and mock flows, read the constructed prompt in full,
   write hypotheses and budget, and let the user run the paid command. A saved incorrect transcript should remain
   a regression example, not become permission for selective retries until success.

Track intermediate rates: required policy available before answering, correct assessment reason, clarification
before ambiguous proposals, unwanted proposals after completion, unnecessary versus missed handoffs, and factual
explanation accuracy. Keep strict success, pass^3, invalid simulations, unsafe effects, cost and task-level paired
uncertainty. Current data do not justify promising 90–100% performance on future cases.

## What “predict the refund” should mean here

For known trusted facts, code can compute current eligibility and a proposed amount. Customer intent, future
confirmation, staff approval and future state changes remain separate conditions. An eligible assessment must
not be described as a guaranteed completed refund or as a guaranteed bank-arrival date.

The Olist subset contains order/payment history; the project's returns, approvals and refund outcomes are
synthetic. It is not labelled production-refund data for training a reliable approval/arrival predictor. There is
no measured need here for fine-tuning or a new predictive ML model. Improve the existing decision service and the
agent's use of it first.

## External systems and research: what applies

The following are public documented patterns, not independent proof of vendor accuracy or a description of their
private implementations. The proposed adaptations above are this review's inferences from those patterns and
the local evidence. Sources were opened on 20 October 2026.

- [OpenAI function-calling guidance](https://developers.openai.com/api/docs/guides/function-calling): move known
  arguments and predictable work into code, use clear schemas and limit overlapping tools. This supports a compact
  assessment interface and retaining authorization in services.
- [OpenAI agent evaluation guidance](https://developers.openai.com/api/docs/guides/agent-evals) and
  [evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices): inspect
  workflow traces, assess the relevant failure points and grow regression coverage. These principles do not require
  replacing the project's local evaluator with a hosted product.
- [Anthropic on effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents): return useful
  context, refine tool contracts and evaluate realistic tasks. This supports supplying reasons and citations with
  assessments rather than relying on the model to reconstruct them.
- [Anthropic on effective agents](https://www.anthropic.com/engineering/building-effective-agents): explicit workflow
  paths suit predictable steps; add complexity only when measurements justify it. This supports a small amount of
  conversation state rather than a multi-agent rewrite.
- [Gorgias action configuration](https://docs.gorgias.com/en-US/create-an-action-for-ai-agent-567325): conditions,
  ordered steps and customer confirmation control when actions run. Retain the project's explicit approval flow
  and define action preconditions clearly.
- [Fin escalation rules and guidance](https://fin.ai/help/en/articles/13976161-manage-fin-ai-agent-s-escalation-guidance-and-rules):
  distinguish offering escalation from carrying it out and combine structured triggers with conversational
  guidance. This directly informs the proposed handoff decision table.
- [Anthropic on agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents): validate graders,
  examine specification ambiguity and distinguish partial outcomes without losing overall success requirements.
  This supports adjudicating the deadline explanation and dynamic handoff examples.
- [The original tau-bench paper](https://arxiv.org/abs/2406.12045): checks final database state and repeated-trial
  consistency. Keep those measurements, alongside communication and safety checks.

## Implementation order

1. Full versioned policy context and source-bearing tool results.
2. Shared read-only assessment, reason priority and zero-paid handling.
3. Policy v2, handoff controls and clarification/completion state.
4. Grounded explanations, matched grader/simulator regressions and controlled development comparisons.
5. Model selection, followed by one frozen new-set evaluation of the selected candidate.

The core financial invariants remain requirements throughout every experiment.

## Preparing for genuinely new cases

Added on 20 October 2026 after the owner clarified that the next assessment will use 20 different scenarios.
The eight interventions above are the workstreams; this section makes their verification broader than replaying
the 20 used cases. It records preparation requirements, not implemented coverage or a guarantee of faultlessness.
The hypothetical 48/60 calculation above applies only to the saved v1 cases and does not predict the new set.

### What the existing tests establish, and what they do not

`tests/test_eligibility.py` already tests several payment methods, invalid payment combinations, delivery-time
problems, refund-window boundaries, discounts, partial prior refunds and exact proposal expiry.
`tests/acceptance/test_concurrency.py` exercises real competing transactions, and
`docs/failure-cases.md` maps recovery, authorization and ledger checks to existing tests.

However, `tests/acceptance/test_properties.py` varies action sequences on only two fixed starting fixtures, D02
and D07. More sequences on those fixtures do not introduce new order/payment/return shapes. Its deterministic
rotating probes and explicit expiry examples should remain: previous mutation runs showed that relying on rare
random choices can leave a known faulty behavior untested. Existing mock conversations establish integration
behavior for their scripts; they cannot establish that an LLM understands unfamiliar customer language.

### Coverage matrix for v1.1 development

For each row, retain the existing positive and negative cases, add the missing combinations, and record the test
or saved development trial that supplies evidence. An unimplemented row remains open, even if other tests pass.

| Area | Variations to exercise | Required result |
|---|---|---|
| Trusted order and return facts | Delivered/in transit; missing or implausible delivery time; all/some/no requested units returned; earlier refund; exhausted balance | Correct eligibility and primary reason; no customer claim changes trusted facts |
| Money and selection | One minor unit; whole amounts; allocated discounts with rounding; shipping; repeated products with distinct unit IDs; free-only and mixed free/paid units | Exact paid refundable amount; explicit excluded units; no zero-value ledger line or silent selection change |
| Payments | One supported record, several records, missing/invalid records; request for another destination | Apply the specified policy; distinguish refusing a destination change from rejecting the legitimate refund |
| Time and freshness | Immediately before/at/after the refund deadline and proposal expiry; changed order or policy after assessment/approval | Preserve the distinct inclusive refund deadline and strict proposal expiry; revalidate before any write/payment |
| Ownership and authority | Foreign customer/order/unit/proposal; another conversation of the same customer; forged staff claims and replayed events | No unauthorized disclosure or effect; rightful authorized requests and retries still work |
| Meaning and clarification | Paraphrases, minor typos, pronouns, duplicate product names, explicit IDs, all-units requests and changed intent | Ask where selection remains ambiguous; use clear selections without unnecessary questions; confirm the actual selected set |
| Completion and handoff | Informational question; thanks after receipt; future return; genuinely new request; explicit human request; required manual review; unsupported subrequest followed by acceptance | No unintended new proposal; appropriate handoff with an evidenced reason; necessary human requests honored |
| Untrusted content | Customer/seller notes containing fake approvals, inflated amounts, policy claims or tool instructions alongside a legitimate request | Trusted fields and authority stay unchanged; handle the legitimate request when possible |
| Recovery and competing actions | Retries with same/new/conflicting keys; lost answers; restart; overlapping refunds; cancellation/handoff racing execution | A permitted transactional outcome, at most one effect, truthful status and the same receipt for rightful retries |
| Customer-facing facts | Amount formats, delivery-based deadline, original payment, paid versus pending state, payout timing and relevant policy IDs | Supported explanations; no invented approval, completion, bank-arrival promise or irrelevant citation list |
| Evaluator and simulator | Equivalent valid wording, wrong amount/date anchor, invalid customer behavior, multiple applicable reasons and explicit requests arising later | Independent expected outcomes; distinguish tool/agent/simulator faults; retain every unsafe effect and all scheduled trials |

This matrix is bounded by the one-shop, one-currency, English-language simulated refund flow. It does not add
other support products or assert coverage of every possible input or sequence.

### How to exercise combinations without learning the final questions

1. Add generated, valid synthetic fixtures to the free domain/stateful tests, varying trusted facts as well as
   action order. Keep invalid API arguments as separate rejection tests. Record the generated example/seed on
   failure, and assert that the run reaches both allowed refunds and refused actions.
2. Define finite levels for each matrix dimension. Cover pairs of those levels and explicit higher-risk
   combinations, rather than claiming to enumerate an unlimited Cartesian product. Include discount + previous
   partial refund + multiple units; ambiguous selection + change of intent; and stale assessment + changed order.
   Retain the existing expiry + committed receipt + retry and concurrency checks.
3. Check relationships between related cases. Reordering explicitly selected unit IDs must preserve the result;
   consistently renaming IDs must preserve the result and access relationships; changing only seller prose must
   not change numeric eligibility; moving ownership to another customer must remove access. State the assumptions
   for each relationship, so that a genuinely changed customer selection is not treated as equivalent.
4. Pair language variants with the same intended outcome, including straightforward successes. Also pair required
   handoffs with superficially similar cases that need no handoff. Do not obtain a better refusal score by making
   the agent refuse every request or route everything to staff.
5. Use hand-authored expected values and database/event checks. The independent evaluator must not import the new
   assessment function to decide whether that same assessment is correct. Review ambiguous business choices
   before grading them, preserving historical v1 rules and judgments.
6. Recheck targeted planted faults against a passing baseline. A database/setup error is not a caught business
   defect. Give each named defect a reliable trigger; do not rely solely on increasing the random example count.
7. Run language-understanding comparisons on development data after the free checks. Mocks cannot substitute for
   those measurements. Before any paid batch, save the full prompt inspection, predictions, trial set and budget;
   the owner runs the command. Include all trials, not just successful reruns.

### Gates before the next final evaluation

- Each implemented workstream has positive, negative and relevant boundary tests, with all identified defects
  fixed or explicitly recorded as unresolved. No known required safety defect is accepted to improve a score.
- The free suite, authorization table, recovery/concurrency checks and affected browser flows pass with the
  required database/browser present. The new assessment has no write effects, and later checks catch stale facts.
- Development comparisons show which intervention helped, including per-family failures, unnecessary/missed
  handoffs, cost and uncertainty. Policy v2 results are distinguished from policy v1 comparisons.
- The final candidate, policy, simulator, grader and targets are fixed before evaluating the 20 new cases.
  Preserve the old held-out files and run; use versioned development copies for diagnosis. New cases follow
  predeclared coverage rules and include new situations/combinations, not just renamed failures. If an independent
  author is available, their review improves separation; otherwise disclose the author's knowledge of the system.
- Open the new set for one declared final batch with three trials per scenario and the declared comparisons.
  Report any remaining failures. Reusing its outcomes to tune another version spends that set as held-out evidence.

Passing these gates increases the evidence for generalization within the supported flow. Neither the matrix,
the number of tests nor a successful batch proves that an unseen scenario cannot expose another defect.

## Final consistency check of the policy v2 table

20 October 2026. This is the recommended implementation specification for the ten-row policy table supplied by
the owner. It refines section 3; it does not declare policy v2 implemented, business decisions approved, or the next
evaluation passed. No production policy, financial service or frozen scenario was changed by this review.

### Evidence and verification

Compared all twelve policy v1 sections with `docs/product-contract.md`, `refund_agent/eligibility.py`,
`refund_agent/refunds.py`, `refund_agent/agent/tools.py`, `prompts/agent-v3.md` and the policy, eligibility,
replacement, cancellation and handoff tests. Seventy existing free tests passed in `test_policy.py`,
`test_eligibility.py`, `test_agent_tools_shape.py` and `test_independence.py`. The initial sandbox run had three
temporary-directory setup errors; the same selection passed outside that restriction. These are baseline v1
checks, not tests of the proposed v2.

Four additional calls to the current pure decision function verified its overlap behavior:

| Current facts, with all other prerequisites satisfied | Current v1 decision |
|---|---|
| Late request with a qualifying earlier on-time request | `needs_person`, reason `window` |
| Same timing, but the selected unit has not been received back | `refused`, reason `return` |
| Several payment records and an unreceived selected unit | `refused`, reason `return` |
| Several payment records and a received selected unit | `needs_person`, reason `payment` |

Those calls supplied the earlier-request flag directly; they do not validate the database history lookup or a
conversational claim about that history. The free-only and mixed free/paid examples from section 6 were also
reproduced: both still return `eligible` despite containing a zero-value financial line.

### Corrected reading of the ten rows

| Draft row | Recommended behavior and qualification |
|---|---|
| 1. Customer asks for a person | Honor a clear request for the current conversation, including after a refusal or a completed refund. Record the request/evidence. A completed refund stays paid; an open proposal is invalidated when handoff commits. |
| 2. Backend says a person is needed | Follow the backend's final `needs_person` decision after reason precedence, not a raw missing-data flag. This is a handoff. Routine staff approval of an eligible proposal is a different step and must not cause handoff. |
| 3. Customer says the return was already sent, but receipt is not recorded | Explain that no refund for those units can be paid on that claim. Hand off for a record check. Distinguish this from saying the items will be sent in the future. |
| 4. Customer asks for more money or another destination | Refuse the unsupported subrequest, explain the allowed amount/destination and offer the otherwise eligible refund. A new currency cannot be selected either. Continue only for the exact supported proposal; named mandatory handoff cases still apply. |
| 5. Customer requests an exception, such as being a few hours late | Refuse a hard-rule override. An explicit request for a person is honored. A qualifying earlier on-time proposal is a named review route, not a staff override of expiry or permission for a late automatic payment. |
| 6. Original card is cancelled | A customer's card-cancellation statement does not itself invalidate an otherwise valid original test payment record. Explain the original-destination restriction and continue if accepted and otherwise eligible. Do not guarantee that a real issuer will credit a replacement card. |
| 7. Customer asks when money reaches the card | State the actual backend status. A committed demo receipt proves the simulated refund only; it cannot prove arrival at a bank. A stored receipt from an authorized status read is sufficient to report an earlier refund; do not execute an old proposal to obtain it again. |
| 8. In-transit order and a cancellation question | Explain that cancellation is outside this flow, offer staff help and hand off when the customer accepts. A report that a delivery never arrived is a separate named review condition. Do not invent a cancellation or a return shipment. |
| 9. Customer accepts the amount or will send another item later | Before payment, continue the existing proposal through the customer's button and staff approval. After a receipt, acknowledge without a new proposal. A future return does not create a request now or cancel a valid pending one. A genuinely new refund request is assessed normally. |
| 10. A unit has zero paid amount | Explain that no money was paid for that unit. Do not create a confirmable zero-only financial proposal. If other units qualify, clearly identify the positive-value subset and excluded units, then obtain confirmation for that exact subset. |

For row 6, [Stripe's public refund-destination documentation](https://docs.stripe.com/refunds#refund-destinations)
is precedent for issuer handling and the possibility of failure, not evidence that this application submits bank
refunds. The policy must describe the application's simulated ledger honestly.

### Rules that must accompany the table

1. **Staff approval and handoff are distinct.** Every eligible payment still requires staff approval. Handoff
   transfers the whole conversation, invalidates its open proposal and stops agent writes; it does not grant a
   staff override or provide live staff chat. Say a case was recorded for review only after the handoff succeeds.
   When one item requires mandatory handoff, do not promise that another open proposal in that conversation
   will continue automatically alongside it. Include both items and pending work in the handoff.
2. **Access and exact intent come first.** Reject foreign/unknown IDs without exposing protected data. Clarify
   competing item interpretations before proposing. A request for "all three" with an unambiguous selection needs
   no artificial question. If only some selected units qualify, disclose the exclusions; never silently pay a
   different set.
3. **Financial eligibility and conversation routing are separate decisions.** For the same candidate unit set,
   retain a definitive policy refusal ahead of an incidental payment/data review condition; for example,
   shipped goods with multiple payments are refused for order status, not automatically routed for split payment.
   Evaluate a proposed eligible subset separately. A direct human request or a named dispute/shipping-review
   condition can still require handoff even though money is refused. Thus "human only when requested" applies
   only when no named mandatory review condition is present.
4. **Name the manual-review cases.** They include the final backend `needs_person` result, a return reportedly sent
   but not received, a reported delivery that never arrived, and a request to refund shipping charges. An
   informational question about shipping charges is answered from the policy; it is not itself a shipping-refund
   request. Other unsupported services receive an explanation and an offer of staff help. A generic request to
   ignore a hard refund rule does not itself create a discretionary refund power.
5. **Keep the two time limits distinct.** The existing request window is inclusive at the exact deadline,
   measured from trusted delivery time to proposal creation. The proposal validity limit is strict at expiry.
   Reading an assessment or typing a message does not reserve funds or extend either time limit. Confirm, decide
   and execute must still validate current state; a committed receipt survives expiry.
6. **Define the earlier-request route per unit.** Use recorded history for the same unit IDs; customer statements
   are not evidence. Paid, rejected or customer-cancelled proposals do not qualify as expired/invalidated history.
   `_earlier_request_on_time` currently returns one boolean if *any* selected unit has such history. The new
   assessment must expose which units qualify and must not give unrelated newly added units that status.
   Another hard refusal, such as a missing return, still blocks that financial candidate; a reported record
   discrepancy may separately trigger handoff.
7. **Respect the proposal lifecycle.** An eligible replacement may supersede an unconfirmed proposal. After
   confirmation, changing the financial selection requires the customer to cancel the old proposal through its
   authorized control, followed by a new proposal, confirmation and approval. The agent cannot cancel as the
   customer or reuse approvals. Explain a staff rejection using the stored reason and do not automatically
   re-propose to evade it. A committed refund cannot be cancelled through this flow.
8. **Handle an unresolved change request conservatively.** If the customer requests cancellation or a selection
   change while payment is pending, guide them to the authorized cancellation control and do not initiate a new
   execution while that request is unresolved. A chat message is not proof that cancellation committed; read
   current status and report any already committed receipt truthfully. Exercise this together with a delayed
   approval notice, so resumed agent work respects the current conversation intent.
9. **Use current facts and truthful status.** An assessment is informational and can go stale. Recheck at proposal,
   approval and execution as applicable. A failed read or timeout is not proof of ineligibility or of a payment.
   Do not claim a human was contacted, an approval granted, a cancellation performed or money paid from the
   model's own text. Use committed backend evidence.
10. **Keep v1 and v2 separately reproducible.** Store the new controlled policy with its own version/hash, render
    its documentation, and use matching prompt, tools, scenario expectations and evaluator inputs. Keep the
    historical v1 source/hash and run. Version selection must be explicit when replaying v1 versus running v2;
    changing a global default must not silently reinterpret frozen old scenarios. The product contract's policy
    source/citation wording and handoff examples must also match the new implementation.

### Acceptance cases required before round two

These are implementation requirements, not assertions that the cases already pass. Existing matching tests can
be reused; new v2 behavior needs its own tests and saved development evidence.

| Case family | Required evidence |
|---|---|
| Eligible baseline | Correct exact amount, card confirmation, staff approval and one receipt; no unnecessary handoff |
| Typed acceptance before/after payment | Before: no payment from a typed yes; after: no new request; pending approval is not reported as completed |
| Future return while another request is pending | Explanation only for the future item; existing eligible work is preserved |
| Multiple reasons | Shipped + missing return + multiple payments, and late-history + missing return: correct primary refusal; add an explicit human/dispute request and verify routing changes appropriately |
| Mandatory review with eligible-looking other items | Handoff stops the whole conversation and invalidates pending work; no promised parallel automatic refund |
| Shipping information/refund | Information alone does not trigger handoff; an actual shipping-refund request does; no shipping money enters the automated ledger |
| Delivery/return dispute | Distinguish a reported discrepancy from an ordinary in-transit status or a future return; claims never change trusted records |
| Excess amount/new destination | Allowed alternative works when accepted; refusal of the alternative does not become confirmation; explicit human requests are honored |
| Cancelled original card | With a valid original test record, no invented destination or guaranteed bank arrival; invalid/multiple records still follow assessment |
| Free and paid units | Zero-only, mixed free/paid, and mixed free/ineligible-paid sets; explicit exclusions, positive financial lines, no empty confirmable proposal |
| Time boundaries | Before/at/after both limits; assessment before the request deadline and proposal after it; an already committed receipt remains readable |
| Earlier-request history | Same units, disjoint units and partial overlap; expired/invalidated versus rejected/cancelled/paid history; no inherited entitlement for newly added units |
| Selection ambiguity and changes | Same-name products across orders, explicit all-units selection, replacement before confirmation, cancellation before replacement after confirmation |
| Cancellation or change with a delayed approval notice | No new agent execution while the customer's request is unresolved; authenticated cancellation versus an already committed payment is reported correctly |
| Staff rejection and completed status | Give the stored rejection reason; no invented refund or automatic proposal to evade rejection; historical receipts are reported through reads |
| Retry, restart and races | Existing at-most-once, rollback, cancellation/handoff and freshness checks pass; adding new conversation state does not break recovery |
| Tool/system failure | No fabricated policy denial, receipt or handoff; recover from the actual saved state |
| Policy and evaluation identity | Matching versioned policy and relevant citations throughout; v1 remains reproducible; independent expectations and simulator behavior agree before live runs |

Before the final batch, attach the passing implementation evidence to these families, run the free suite and the
declared development comparisons, and freeze the candidate and targets. The next 20 cases remain unused for
tuning. Any unresolved family is visible in the handoff and release assessment; this review is not a statement
that every possible future defect has been excluded.
