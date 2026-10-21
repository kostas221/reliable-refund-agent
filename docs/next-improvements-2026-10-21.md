# Improving v1.1 while protecting the measured gains

21 October 2026. For the project owner and implementing engineer. This is an evidence-based execution guide for
the existing v1.1 cycle, especially the step 2 approved in the plan's 21 October entry. It complements
`improvement-review-2026-10-20.md`; it does not reopen the product scope or change the frozen business policy.
Recommendations below are proposed experiments, not completed fixes or predicted gains.

## Recommendation

Keep policy v2, the current financial controls and the single-agent architecture. Complete the approved tool
improvements, then prioritize exact item selection and truthful handoff intent. Preserve a measured baseline and
compare one coherent change at a time. Add a small balanced development set before the new held-out evaluation.
Use model comparisons only after the workflow defects have been addressed.

Do not repeat the previous review's completed work. The current code already checks return disputes against the
named units, checks the latest relevant shop decision for freshness, and gives recovery instructions that do not
generically offer a person after a refusal. Those changes now belong in the regression checks.

## 1. What the latest evidence supports

Baseline: `runs/pilot-20261020T170431Z-gpt-6-luna-none`, implementation commit
`9b6440c17988507d92c02ff2a63af491bf4796f8`, clean at execution. Policy v2 hash:
`49c40ec9f72b3b2e22b7b90b3e8755b1ca1bd0a776436435135cc65931de97b0`.
The manifest identifies instructions v5, agent Luna/none, simulator Luna/low, and three trials for each of thirty
development scenarios. The results are recorded in `docs/pilot/results.md`, section "v1.1 step 3".

| Measure | Current baseline | Why it matters |
|---|---:|---|
| Strict success | 77/90, 85.6% | Includes two incomplete simulations as unresolved |
| Success among valid simulations | 77/88, 87.5% | Secondary view; never substitutes for 77/90 |
| Scenarios successful in all three trials | 23/30 | Consistency, not merely a good average |
| Former held-out scenarios, now development copies | 53/60 | Up from 36/60 at step 1; already used for tuning |
| Required handoffs completed | 18/18 | Protect this while reducing unnecessary handoffs |
| Forbidden handoffs | 4 | Three falsely labelled as customer requests; one followed a genuine request |
| Required clarification before a proposal, D09 and D17 | 0/6 | Largest remaining repeated behavior failure |
| Required citations in D11-D30 | 26/27 | Preserve the citation improvement |
| Unauthorized or duplicate refunds | 0/90 | No observed incident, not proof of zero risk |
| Evaluation cost | $0.0487 | Agent $0.0384; simulator $0.0103 |

The thirteen unresolved conversations comprise six clarification failures, three unsupported customer-request
handoffs, one unnecessary handoff after confusing payment explanations, one missing citation, and two provider
403 errors in the simulator. This decomposition identifies priorities; it does not imply that fixing a category
will add that many successes in a new stochastic run.

The paired improvement over step 1 is +14.4 percentage points, with a 95% interval from +0.0 to +28.9. Against the
earlier v1 runs across all thirty scenarios it is +7.8 points, with an interval from -8.9 to +24.4. D07 and D19 have
changed expectations: the unchanged-expectation subset is 71/84, versus 61/84 at step 1. Report these distinctions.
The saved audit is Claude's; the owner's review is still pending. These are development results, not an estimate
for the next twenty unseen cases.

## 2. External practices worth adapting

Primary sources checked on 21 October 2026. These are documented practices and an inspectable benchmark, not
evidence that a vendor is better on our tasks. The proposed applications are engineering judgments for this repo.

| Source and documented practice | Application here | Boundary |
|---|---|---|
| [Fin escalation guidance](https://fin.ai/help/en/articles/13976161-manage-fin-ai-agent-s-escalation-guidance-and-rules) distinguishes offers from escalation and warns that broad guidance increases unnecessary handoffs. | Keep narrowly named reasons; distinguish a clear human request, acceptance of a specific offer, and a request for an exception. | Do not import Fin's default frustration/loop rules into our frozen shop policy. |
| [Gorgias Actions](https://docs.gorgias.com/en-US/create-an-action-for-ai-agent-567325) supports conditions, ordered steps and customer confirmation. | Keep prerequisites outside free-form model judgment; clarify the exact selection before a proposal, then retain the existing confirmation and staff approval. | Their documented behavior does not prove equivalent transaction or authorization guarantees. |
| [Anthropic tool engineering](https://www.anthropic.com/research/writing-tools-for-agents) recommends precise schemas, meaningful tool results and evaluation of actual tool use. | Reuse domain logic for assessment; return facts, reasons and next permitted actions; remove model-chosen execution IDs carefully. | A new tool is useful only if measurements show better behavior without regressions. |
| [Anthropic agent evaluations](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) separates capability tests from regression tests and recommends testing when behavior should and should not happen. | Maintain a protection set and paired positive/negative development cases; inspect trajectories and final state. | A scripted test of a guard does not prove language interpretation by the live model. |
| [Sierra's tau-bench paper](https://arxiv.org/abs/2406.12045) evaluates simulated conversations with tools and policy against database goals and repeated-trial reliability; its [retail policy](https://github.com/sierra-research/tau-bench/blob/main/tau_bench/envs/retail/wiki.md) makes identity, exact item IDs and confirmation explicit. | Retain state-based checks and pass^3; exercise variant confusion, changed intent and multiple requests. | Its broader tasks, confirmation mechanism and scores are not comparable with ours. Do not copy its policies or test cases as new held-out evidence. |

## 3. Work in this order

### A. Preserve the baseline and finish the already approved tool change

Keep the baseline manifest, prompts, results and audit intact. Work in small reviewable commits; make it possible
to compare or restore a candidate without mixing prompts, tool schemas and domain code from different versions.
Use the existing protections for predictions, budgets and run identity.

Complete step 2 as already approved: `assess_refund` instead of policy search, backed by the same data loading and
eligibility logic as `propose`; amount citations for eligible proposals; evidence for `customer_asked`; execution
resolved from the current conversation rather than a proposal ID chosen by the model. Keep unrelated wording and
policy v2 fixed for this measurement. If these changes run together, describe the result as a package comparison,
not as the isolated effect of assessment.

Before a paid comparison, prove:

- Assessment writes no proposals, confirmations, approvals or ledger entries and exposes only the customer's
  data. It matches proposal eligibility on identical facts and time, including multiple reasons, zero-value
  units, previous requests per unit, expired requests and invalid payment records.
- Assessment describes financial eligibility, not customer intent. Two eligible units do not imply the customer
  requested both. Assessment does not reserve the request window or approve a payment.
- `shop_decided` can use a current authoritative assessment without a dummy proposal; handoff rechecks its
  supporting facts rather than trusting a model's assertion that assessment returned `needs_person`.
- Removing the execution argument preserves identity across retries. After a committed refund there may be no
  open proposal: retry must still return the original receipt. An old call must never resolve to a later request
  and pay it. Test a new proposal appearing between attempts, restart before checkpoint, cancellation and handoff.
- The domain authorization checks remain in force. A routing helper must not silently change what configuration
  C disables; continue its authorization-table comparisons and disclose any changed experimental reachability.

**Small consistency issue found during this review:** `reads.orders` currently marks a unit received when
`received_back_at IS NOT NULL`, while `_policy_order` and execution also require that timestamp to be at or before
the supplied clock. With a future timestamp, the customer/agent read can disagree with the backend. This is a
code-inspection finding, not a cause established for the latest failed conversations. Include before/at/after
receipt-time cases in the shared-facts checks and align the read with the existing business rule.

### B. Treat customer-request evidence as provenance, then test its meaning

The proposed quoted-text check is useful but insufficient. "Where is my order?" is a genuine customer message
and still does not ask for a person. Nor does "I do not want a human" become consent because it contains a keyword.

Bind evidence to a message ID, its role and this conversation. Preserve enough context to distinguish a direct
request from acceptance of a particular offer. A "yes" needs the relevant preceding offer; a "yes" to the refund
amount is unrelated. Do not search arbitrary historical substrings or trust a model-supplied consent boolean.
The backend can prove provenance and order, not the meaning of unrestricted language.

Exercise this before claiming that the three false handoffs are fixed. For uncertain intent, ask one neutral
clarifying question; retain the existing authenticated "Talk to a person" control as a reliable route. Clear
requests must still be honored without creating a refusal loop. Do not require every customer to use a button
as a new business rule. If the model still misclassifies real quotes, compare a narrowly scoped intent check in
its own experiment; another model's judgment would remain fallible and its cost must be counted.

Report separately: the tool call's actor, the model's claimed reason, the supporting customer message, and the
reviewed origin. The existing `origin=customer` is not proof that the customer initiated the action. Keep legacy
fields compatible if adding evidence; do not rewrite historical logs. Apply the same language tests to
`shipping_refund`, which also relies on the model's interpretation.

### C. Fix clarification before proposing, without adding unnecessary questions

This is the largest remaining quality problem: six failures across two scenario families. The trace shows the
agent already saw the competing returned items. Lack of eligibility information is not a sufficient explanation.
The association with policy search or prompt placement is a hypothesis, not a measured causal effect.

Measure clarification in step 2. If it remains poor, make the next experiment only the already contemplated
ordering of policy and behavior instructions, with a concise rule at the action boundary. Do not simultaneously
change the model, simulator, examples and tools. A better run on D09 alone is not enough.

If that small experiment is inadequate, use the existing graph to track the current selection and an unresolved
clarification, with the customer message that resolved it. A known unresolved selection cannot create a proposal.
Changes in the customer's request must invalidate the old selection. Keep this state conversational: it grants
no confirmation, approval or refund rights, and the backend still validates the proposed exact units.

Do not treat "more than one returned unit" as an automatic need for a question. "Both shirts", an exact size or
a unique order reference may already identify the requested set. Conversely, do not treat a model-generated
`selection_confirmed=true` as independent evidence of intent. Test the resolver with paraphrases and adversarial
phrasing; it cannot be made infallible by adding a field.

### D. Ground completed-refund answers in the receipt

D08.try3 completed the refund correctly, then lost the conversation because its answers made the customer doubt
the original-payment status. The genuine later human request must still be honored; fix the preceding explanation.

Expose only the necessary authorized receipt facts, including the original payment reference where available.
Use existing status reads to distinguish a completed refund from current eligibility for a new refund. An
assessment returning "already refunded" does not invalidate the historical receipt or mean the original payment
never qualified. Do not expose full payment credentials.

A short completion message should identify the simulated refund, amount and receipt. Answer a timing or banking
question truthfully and cite payout when relevant. Keep the demonstration's limitations visible and never imply
a real bank transfer. Avoid adding a lengthy generic banking explanation to every successful turn. Confirm that
this wording change preserves remaining/payout citations, customer understanding and honest demo claims.

### E. Keep infrastructure failures distinct and compare models last

The two D10 errors were provider 403 responses during the simulator's final turn, after a correct handoff. Record
role, status, trial and a provider request ID when available, without credentials. Do not reinterpret these as
refund-policy failures, introduce blind permission-error retries or silently replace failed trials.

Keep strict success and valid-simulation success side by side. A supplementary rerun, if justified, gets its own
identity and report. Check simulator behavior and the human audit sample before relying on the final score.

After the above behavior is stable, compare the already planned Luna and Sol configurations on the same final
development candidate, simulator and scenarios. Judge success, consistency, latency and agent cost per resolved
case. The old model comparison used a different system; it cannot select the winner for v1.1. Defer selective
model routing until measured failures and cost justify its added complexity.

## 4. A small generalization set, written before its candidate runs

Add twelve development cases in six contrasting pairs. Use new products, amounts and wording; write expected
behavior from the policy before reading any candidate output. These are development cases, never new held-out
claims. Repeat each three times for thirty-six conversations and report pairs/families together.

| Pair | One case | Its contrast |
|---|---|---|
| Item selection | Two plausible sizes, vague request: ask first | Same records, explicit request for both: proceed |
| Order selection | Similar products in two orders: clarify | Exact order/item reference: no unnecessary clarification |
| Handoff meaning | Shipment-status or hard-rule-exception request: answer | Clear request for a staff member: hand off |
| Contextual acceptance | Yes to a current offer of staff help: hand off | Yes to the amount, or explicit rejection of staff help: do not infer handoff |
| Shipping intent | Informational question about shipping charges: answer | Actual shipping-refund request: named handoff |
| Completion and changing intent | Receipt followed by thanks/timing question: answer from status | A genuine new item or unresolved cancellation: handle the new intent without paying the old one again |

Supplement with free deterministic checks for foreign message references, negation/quoted text handling where
applicable, evidence ordering, changed selection, delayed approval, time boundaries and the financial invariants.
Include restarts and retries for any new graph state. A scripted resolver test proves the routing given a state;
live development trials are needed to assess whether the model identifies that state correctly.

## 5. Gates for retaining a change

The following are proposed development screening rules, not statistical guarantees or a revision of final targets.
Write them and the expected cost in the experiment's predictions before its paid run.

| Check | Proposed gate |
|---|---|
| Safety and authorization | All relevant deterministic checks pass; any unauthorized/duplicate committed refund blocks promotion regardless of total score |
| Required handoffs | Preserve 18/18 on the thirty-case set; investigate any loss before retaining a routing change |
| Citation improvement | At least 26/27 on the same required items; review every new omission |
| Protected successes | Review every failure in the 23 scenarios that previously passed all three trials; do not hide losses behind gains elsewhere |
| Main target | For a clarification candidate, aim for 6/6 correct clarification sequences in D09/D17; for a handoff-intent candidate, no false customer-request handoffs in the targeted repeats. Both must also pass the new positive/negative cases; these small counts are screening goals, not guarantees. |
| Overall score | At least the observed 77/90 and 23/30 pass^3 for screening; these alone do not prove non-regression or generalization |
| Operational behavior | Bounded calls/retries, truthful completion, and no extra handoff/clarification loops |

If a stochastic case regresses, inspect it before accepting or rejecting the design. Where another run is needed,
predeclare a matched baseline/candidate batch and retain both outcomes; do not retry only failures until they pass.
Report paired differences and uncertainty by scenario, grouping related variants by family. A small sample cannot
establish equivalence. Keep the unchanged-expectation comparisons available.

For each candidate: targeted free tests first, then the appropriate existing suite, mock end-to-end, and inspection
of one full logged prompt and tool schema. Record a coherent version, predictions and a runner-enforced cap. Paid
runs remain user-run; the historical $0.0487 is not a price guarantee. Recheck the current cost estimate before
issuing commands. One change must earn promotion before the next is stacked on it.

## 6. Boundary before the next twenty held-out cases

Freeze the final candidate, policy, simulator, grader, targets and audit rule before opening the new set. Keep
old results unchanged. The 53/60 result used known development copies and must not be presented as an unseen-case
score. Do not loosen criteria to make a failing trace pass; a genuine evaluator defect requires a documented
correction applied consistently to baseline and candidate saved results.

No new payment provider, autonomous refunds, policy exceptions, multi-agent framework, fine-tuning or larger
retrieval system is justified by these findings. The current evidence favors a small number of changes to intent,
tool facts and recovery. More complicated ideas need a distinct failure and a controlled experiment first.

Review scope: inspected the saved reports and selected raw failure traces, current policy/tool/graph/read code,
the latest approved plan entry and primary external sources. No application code, policy, scenario or saved run
was edited for this document; no new live model run or full test suite was executed. Existing working changes in
the implementation session must be reconciled before starting any item here.

## 7. Update after step 2: 22 October 2026

This section updates the recommended next experiments using
`runs/pilot-20261021T211812Z-gpt-6-luna-none` (implementation `40ad047`, instructions v6). Earlier sections retain
their dated evidence. The implementation and results are recorded in the latest plan entries and
`docs/pilot/results.md`; this addendum proposes work, not an approved policy or application change.

### What this run establishes

Strict success is 79/90, versus 77/90 in step 3; the paired difference is +2.2 percentage points with a 95% interval
of -5.6 to +10.0. This is not established overall improvement over step 3. Success among valid simulations is
79/89; D15 try 3 is a simulator fault. Pass^3 remains 23/30. The recorded audit is Claude's, with owner review
pending. These remain development results.

The mechanisms are more informative: no observed false customer-request handoffs, six refused handoff attempts
followed by recovery, D21 passing 3/3, and citations at 26/27. Clarification is still only 1/6. Required handoffs
fell from 18/18 to 17/18. The 65/69 protected successes clear the predeclared threshold of 63 but include four
regressions; meeting that threshold does not mean every previous gain was preserved.

The previous review's future-return timestamp inconsistency and execution retry concerns have now received
code fixes and tests, as documented in the plan. Do not reopen those changes without new evidence. Retain the
implementation's proposal record for `shop_decided`; this review does not renew the earlier suggestion to remove
it, which was declined because it is the staff-visible case record.

### First measurement: repair the two reported regressions and action-status wording

Keep the proposed repair batch, with one additional, separately graded defect. If these repairs are measured
together, attribute the outcome to the package, not to any one sentence.

1. **Separate refund eligibility from mandatory case routing.** A refusal to refund does not override a named
   handoff in the policy. In D22 try 2, the customer says the return was already sent, the records do not show
   receipt, and the assessment's generic refusal instruction is followed by an optional offer instead of the
   required handoff. Make recovery instructions conditional on the policy's actual cases and the relevant order
   and units. Do not convert every unreceived item or every refusal into a handoff. Contrast "I sent it" with
   "I will send it later"; retain normal refusal for a deadline exception and honor a genuine human request.
   The backend can verify record facts; interpreting a claim in unrestricted customer language remains fallible.

2. **Separate original-payment destination from the demo's execution limits.** After a successful execution,
   ground the response in the receipt's amount, original payment and receipt number. A suitable English example
   is: "In this demo, your refund of BRL 49.90 has been recorded against the order's original payment. Receipt R."
   Fill the values from the actual receipt. Preserve required citations. Explain the simulated ledger and the
   absence of a real bank transfer when relevant to a timing/payment question, without introducing that extended
   explanation into every successful turn. Never imply bank settlement, invent an arrival date, or say that the
   recorded refund does not go against the original payment. Keep the demo identity visible. D01/D11 show why
   this distinction matters; blocking the genuine human requests caused by confusion would be the wrong repair.

3. **Describe actions from the latest authoritative result.** D17 tries 1 and 2 contain a saved proposal followed
   by the claim that no proposal exists. This is an independent truthfulness defect even when clarification also
   fails. The assessment currently says "Nothing is proposed or reserved yet"; prefer a statement scoped to its
   own effect, such as "This assessment does not create or change a proposal." Assessment cannot establish that
   the conversation has no existing proposal. The proposal tool already returns its ID and status: use those
   facts after proposing instead of repeating an earlier assessment's wording. Reusing the earlier phrase is a
   plausible explanation for D17, not a proven cause. Grade claims against the event history at the time of the
   message, including existing-proposal retries, cancellation and handoff. Do not automatically cancel a valid
   proposal merely to make an incorrect sentence true, or weaken any customer/staff approval requirement.

### Second measurement: one bounded clarification experiment

Keep policy first, behavior instructions last, with a concise reminder at the proposal boundary. State the
decision positively: identify the requested units from the customer's words; if multiple selections remain
plausible, ask and wait before proposing; if the customer explicitly requests both, proceed with both. Financial
eligibility alone is not evidence of selection. Keep the policy content, model, simulator and domain checks fixed.
Ordering plus a new reminder is one prompt package; its result cannot isolate the effect of ordering alone.

If this still misses the predeclared clarification checks, do not keep adding general prohibitions. The next
candidate should represent the current requested selection and unresolved clarification in the existing graph,
with the customer message supporting the selection. A known unresolved selection blocks proposing, and changed
intent invalidates the previous selection. This state grants no financial authority. A model-generated boolean
does not prove intent; test the interpretation as well as the guard. Explicit requests for both items must not
become unnecessary clarification loops. Evaluate that change separately, including restart and stale-state cases.

### Checks that prevent a better average from hiding another regression

Before paid runs, use free contract and mock checks for the changed tool outputs, routing and financial controls.
Mocks establish behavior given their scripted choices; they cannot establish that the live model understands
the customer's words. Read the complete new instructions and one logged request, record predictions, and retain
the user-run budget cap. Add the truthfulness diagnostic before comparing candidates, applying it to both saved
baseline and candidate traces; do not silently rewrite historical verdicts or count the same failed conversation
twice.

Use the existing thirty-case development set and the planned contrasting development cases. Ensure the contrasts
cover vague one-item requests versus explicit requests for both, past versus future returns, ordinary receipt
acknowledgments versus timing questions, and true versus false human requests. Vary products and wording; do not
read or tune on the next held-out set. Keep case-specific language out of the production instructions.

Proposed screening targets, to write into predictions before running:

- No unauthorized or duplicate committed refunds; retain all relevant authorization and retry checks.
- Restore 18/18 required handoffs and retain zero observed unsupported customer-request handoffs. Six blocked
  attempts in one run do not establish perfect language interpretation.
- Preserve at least 26/27 required citations. Aim to recover the four protected losses, reporting the full 69
  trials and reviewing any new regression rather than relying only on the old threshold of 63.
- For the clarification candidate, target 6/6 in D09/D17 and correct behavior on both sides of the contrasting
  cases. For both candidates, require no observed false proposal/payment/handoff status claims.
- Report 79/90 and 23/30 as the current comparison baseline, alongside simulator validity, cost and paired
  uncertainty. Neither a small increase nor a clean targeted batch proves generalization. If another comparison
  is needed, predeclare a matched batch; do not rerun only failures until they pass.

### External evidence and its limits

Primary sources checked again on 22 October 2026:

- [Fin Procedures](https://fin.ai/help/en/articles/13976254-building-fin-procedures) documents explicit conditions,
  positive/negative triggering examples, and the risk of broad guidance firing during a procedure. This supports
  narrowly scoped recovery and payment explanations here; it does not justify importing Fin's escalation policy.
- [Anthropic's tool engineering guidance](https://www.anthropic.com/research/writing-tools-for-agents) emphasizes
  clear tool boundaries, informative results and evaluation of actual tool use. Our application is to distinguish
  assessment from a recorded proposal and to check recovery, rather than assume more prose guarantees obedience.
- [Claude prompting guidance](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
  recommends placing long documents before instructions in its long-context discussion, explicitly framed around
  inputs of 20,000 or more tokens. That is not direct evidence for this project's shorter prompt and different
  model. Prompt ordering remains an inexpensive hypothesis to test, not an established fix for D09/D17.

No source establishes that a competing product would score better on our cases. The proposed adaptations are
engineering judgments grounded in this run. No business-policy relaxation, new model, extra agent, or architecture
replacement is supported by these failures. This update changes only this review document; no application code,
policy, saved result or scenario was edited, and no paid run or test suite was executed for it.
