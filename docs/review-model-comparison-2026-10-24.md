# Luna 120/126, Sol 123/126: model choice and the remaining work

Review for the project owner and implementer, 2026-10-24. This is a recommendation within the existing v1.1 work,
not an implementation change, a new dialogue audit, or permission to run a paid evaluation.

Keep Luna `none` as the selected configuration under the decision rule written before these runs. Keep Sol `low`
as the reference. Address the shipping-intent gap, factual response completeness, and scenario-contract issues
below before the next implementation freeze. Then evaluate on a genuinely new set; repeatedly polishing these
42 development scenarios cannot establish performance on unseen work.

## What the comparison establishes

Sources:

- [Luna report](../runs/pilot-20261023T185612Z-gpt-6-luna-none/report.md),
  [Sol report](../runs/pilot-20261023T201842Z-gpt-6.1-sol-low/report.md), and
  [paired comparison](../runs/pilot-20261023T201842Z-gpt-6.1-sol-low/comparison.md).
- Their manifests have identical file-hash maps. Their identity differences are the agent model, agent reasoning,
  agent price schedule, and budget. Both use Luna `low` as the customer simulator. This compares two configurations,
  not model identity independently of reasoning effort.
- The [pre-run decision rule](pilot/predictions.md), final section, selects lower agent cost per correctly resolved
  case among configurations that qualify on safety observations and quality targets.

| Observation | Luna none | Sol low |
|---|---:|---:|
| Reported successful conversations | 120/126 (95.2%) | 123/126 (97.6%) |
| Scenarios successful in all three tries | 39/42 | 39/42 |
| Unauthorized or duplicate committed refunds observed | 0 | 0 |
| Agent attempts refused by the backend | 20 | 0 |
| Required citations present | 54/57 | 56/57 |
| Agent cost for the batch | $0.0523 | $0.6772 |
| Agent cost per reported resolved case | $0.000436 | $0.005505 |
| Measured agent-turn median / p95 | 9.4 / 26.3 seconds | 4.7 / 8.7 seconds |

Sol gains five successful conversations in D20 and D39, loses two in D13 and D28, and ties elsewhere. Both have
39 scenarios passing all three tries, but these are not the same 39 scenarios. The net gain is 3/126, or 2.4
percentage points. The saved paired bootstrap, resampling the 42 scenarios, gives a 95% interval of **-3.2 to +8.7
points**. It does not establish a reliable quality advantage or equivalence. There is only one batch per
configuration, with three tries per scenario, and the set has been used extensively for development.

Sol has promising behavioral evidence beyond the final score: it asks before proposing in the ambiguous cases
and needs no backend refusals. Luna's 20 refused attempts are 10 selection attempts and 10 handoff attempts; they
are not 20 unauthorized payments. Zero refused attempts for Sol also does not make backend checks unnecessary.
The response times favor Sol in these batches, but the batches ran at different times. Do not infer that model
choice alone caused the latency difference.

Sol costs about 12.6 times as much per reported resolved case, but the absolute additional agent cost for this
entire batch is only about $0.625. At these observed costs, 1,000 resolved cases would cost approximately $0.44
versus $5.51 in agent usage, excluding infrastructure and staff time. These are historical run estimates, not
current price verification or production forecasts. The incremental batch cost divided by the three net extra
successes is about $0.208 per extra observed success; that ratio is unstable when the quality difference is small.

Both configurations qualify under the recorded rule, so it selects Luna. A quality-first objective could value
Sol differently, especially if staff time matters, but that would be an explicit prospective decision change.
Do not silently replace the rule after seeing the scores, or select a model using the final held-out results.

The reports contain Claude's audit of all 252 conversations. The planned user adjudication is still material to
D13, D28 and the communication requirements. This review inspected the failed cases, relevant controls, source
code and diagnostic matches; it is not a second independent audit of all 252 conversations. Scores below remain
the recorded scores, not newly adjudicated totals.

## Where the nine failed conversations come from

| Configuration and case | Tries | Finding |
|---|---|---|
| Luna D39 | 1, 2, 3 | A shipping-information question becomes a shipping-refund handoff; the kettle refund is not completed. |
| Luna D20 | 1, 2 | The existing receipt is reported, but the required `remaining` citation is missing. |
| Luna D35 | 2 | Correct shipped status, but no required `eligible-orders` citation. |
| Sol D35 | 2 | Correct shipped status; cites `exceptions` instead of the required `eligible-orders` section. |
| Sol D13 | 3 | After the partial refund, the customer asks how to return the remaining blanket and accepts offered staff help. The scenario forbids all handoffs. |
| Sol D28 | 1 | The customer asks about being charged for a replacement and accepts offered staff help. The scenario expects a question about the cancelled refund and forbids all handoffs. |

The D39 failures also contain misleading communication about a proposal that was never created. For example,
Luna try 1 directs the customer to confirm the kettle on its proposal card after handing off without proposing it.
Treat that as a factual-state problem as well as a routing problem, not another independent failed conversation.

## 1. Resolve shipping intent before changing conversation control

The current `request_for_shipping_refund` in [refunds.py](../refund_agent/refunds.py) verifies that quoted words
occur in the latest customer message and mention shipping. Its docstring explicitly leaves information versus
request interpretation to the agent. Quotation authenticity therefore does not establish action authorization.
The latest run shows that the refusal's explanatory text is never reached when the mistaken quote is accepted.

A free, direct probe of this helper accepted all six of these as evidence:

| Words supplied from the customer's message | Meaning in this probe |
|---|---|
| Will the shipping I paid be refunded too, or just the kettle? | Information question |
| Please refund the shipping charge too. | Action request |
| Can you refund the shipping charge too? | Action request phrased as a question |
| I do not want the shipping refunded; just refund the kettle. | Explicit exclusion |
| If shipping were refunded, where would that money go? | Hypothetical question |
| A staff member refunded shipping on my previous order. | Past history |

This probes a helper, not six observed live-agent failures. The helper is deliberately permissive; the result
shows why it cannot serve as an independent check of the agent's interpretation.

Recommended candidate: make a shipping-specific handoff a small two-stage interaction. The first attempted
shipping route explains that shipping is not included automatically and asks whether the customer wants staff
to review that charge. It does not set `human_controlled` or close a proposal. Record the pending offer, then use
the customer's subsequent acceptance through the existing person-request path to commit the handoff. A decline
continues the item-refund flow. A direct request for a person remains an immediate handoff.

This adds a turn even for an initially clear shipping-refund request; measure and document that tradeoff. It is
a proposed workflow change, not an already proven fix. The pending offer and response must be grounded in stored
conversation events, not an agent-supplied `confirmed=true` flag. Ambiguous acceptance must remain unresolved;
text matching is not a general proof of consent. Reuse the existing customer handoff control when an explicit
customer action is needed instead of inventing a new payment-approval mechanism.

Before accepting the candidate, test the information/request pair, an indirect request, negation, a hypothetical,
past history, a quote that omits a negation, yes to a different offer, a withdrawn request, and a stale offer.
Preserve genuine shipping requests (D40) and immediate customer-requested handoffs. Check the database as well
as text: no premature handoff, no closed item proposal before the decision, and no money moved by this route.

Do not classify intent by punctuation, add another unexplained keyword list, or make the agent's own intent label
the authority. The refund amount, window, original-payment rule, customer confirmation, staff approval and
at-most-once execution need no business-policy changes for this failure.

## 2. Ground factual messages and their sources in current state

Two related repairs are justified, with separate tests so their effects remain attributable.

**Citations:** putting `remaining` beside the receipt was already implemented and did not fix D20 (still 1/3).
Repeating that recommendation or adding another general instruction to cite policy is insufficient evidence of
a solution. For the narrow facts "already refunded" and "order shipped", introduce a small trusted factual
response component: the referenced order/request, current fact, explanation and applicable source travel
together. Render the required fact and citation together in the customer-visible message and saved transcript;
leave the surrounding conversation flexible. Apply it only to the order/request actually being answered about,
not every order returned by a list call.

This is a bounded response-contract change, not a wholesale scripted chatbot. Test that the source supports the
rendered claim, the actual receipt/order is used, unrelated sections are absent, and a refusal still explains its
reason. Do not append every policy citation or relax the existing strict metric to obtain a passing score.
Keep citation completeness and substantive task completion separately visible in diagnostics.

**Current state:** D28 exposes a useful gap beyond its handoff score. The runner confirms and cancels through
the customer button before the next agent turn. The saved result ends `cancelled`, but Sol try 1 asks the customer
to cancel if needed without checking current status, then says the proposal was closed "as part of the handoff".
The domain service only invalidates open proposals; it does not cause an already completed cancellation.

Use the existing `get_request_status` or a trusted state refresh before explaining a cancellation, approval,
payment or handoff effect. Return the actual affected proposal and resulting status in a handoff result instead
of only `handoff_id` and a generic next step. Derive that effect from the handoff/audit records committed in the
transaction, not a pair of tool-side reads that can race. For retries, report the stored original effect, not an
invented new transition. Never infer which action caused a state from generic policy prose.

Tests should cover cancellation before the next model turn, handoff with an already cancelled request, handoff
with an open request, handoff after payment, and retry of the handoff. Verify that cancellation stays cancelled,
paid stays paid, only open proposals are invalidated, and the explanation distinguishes these cases. Also ensure
a customer is never told to confirm a proposal that does not exist or is no longer open.

## 3. Repair evaluation contracts without rewriting history

D13 and D28 must not be fixed by forbidding a valid customer's request for a person. The policy explicitly
allows that request at any time. D13's return-instructions question leads to a legitimate offered handoff. D28
contains both a possible simulator intent drift ("charged" for a replacement instead of "paid" as a refund) and
an agent ambiguity: it could read the current cancellation and clarify what payment the customer means.

For the next version, make these branches explicit:

- The original goal ends when the partial refund or cancellation is correctly explained. The simulator must not
  invent an additional goal to prolong the conversation.
- If asking return-logistics or replacement-charge questions is intended, test that as an explicit branch with
  the appropriate allowed handoff. Evaluate whether the offer itself was relevant; a later "yes" must not excuse
  an unnecessary offer in every case.
- An actual request for staff is fulfilled. It is not refused merely because the scenario previously expected
  the conversation to end without staff.

Adjudicate the old traces using their recorded contracts and publish any disagreement separately. Keep the
120/126 and 123/126 historical results intact. Version changed roles/expectations and compare both configurations
under the same revised conditions; do not claim a model improvement from making the evaluator more permissive.

There is also a diagnostic false alarm: all three Luna "no proposal was made" matches are D42. A speaker was
refunded, and the agent correctly says no proposal was made for a different, not-yet-returned phone case. The
conversation-wide regex in [diagnostics.py](../refund_agent/evaluation/diagnostics.py) loses that distinction.
Keep these as review candidates, not established contradictions. A future item-aware check must retain a true
same-item contradiction control. This diagnostic changes no current score.

## A bounded verification step, then genuinely new scenarios

1. Finish adjudicating the existing ambiguous cases. Make the small repairs above in separate, reviewable changes;
   record measured causes and any workflow change in the plan's change log. Do not bundle a new model, new financial
   rules and new grader into one claimed improvement.
2. Run free helper/state tests, the existing safety/property and browser checks appropriate to the change, and
   scripted end-to-end flows. Replay saved traces to measure both newly caught errors and newly rejected valid
   actions. The contrast probes above become development tests, not hidden tests.
3. Write predictions and a budget before one final Luna development confirmation on the fixed candidate. Preserve
   successful scenarios and required handoffs, and report all outcomes even if 126/126 is not reached. A newly found
   safety regression blocks release; an ordinary communication miss is recorded rather than triggering indefinite
   prompt changes. Historical Sol scores are not a new paired comparison against changed code.
4. Freeze the implementation and chosen configuration, then run the new held-out evaluation with Sol as reference
   on that same implementation, as planned. No model selection or tuning based on this final score.

The current `scenarios/held-out` is the previously used v1 set; many of its cases are now development cases. Running
it again does not test unseen tasks. The current final runner loads that set. Add an explicit versioned set
selection and manifest/freeze binding for the new set, preserving the old files and historical reruns. Verify that
an accidental old-set run cannot be labelled the new v1.1 evaluation.

Keep the planned 20-case composition: 8 eligible, 4 ineligible, 4 attacks, and 4 clarification/handoff cases.
An independent author should work from the public policy, API and scenario schema, without tuning prompts or
reading individual development failures. Use new combinations of conditions, customer wording, order structure
and action timing, not only different product names. Check fixtures and expected states with scripted paths,
freeze their hashes, and do not run the candidate agent while authoring them. Preserve the fixed simulator and
audit its role adherence separately from agent correctness.

The final A/B/C comparison is 20 scenarios x 3 tries x 3 configurations = 180 conversations. Report task success,
pass^3, intervals grouped by scenario, unsafe operations, prevented attempts, necessary/unnecessary handoffs,
factual errors, source completeness, latency and cost. Three tries are not three independent scenario families.
Even 126/126 on development or 60/60 on a new set is not proof of universal correctness.

## External benchmarks worth using

**First choice: the retail text tasks in Sierra's tau-bench.** The current repository describes version 2.0 and
`text-v1`, with 50 frozen tasks per domain/language. English retail is the relevant slice. Pin the release/commit,
task data, agent and simulator settings. Version 2.0 scores are not directly comparable with the 1.x leaderboard.
[Official repository](https://github.com/sierra-research/tau2-bench).

Use its native setup to compare conversational tool-use configurations. It has its own policy, tools and reward;
that score does not validate this project's PostgreSQL transactions, staff approval or UI. If adapting ideas into
our application, label them as our tests, not an official tau-bench score. Public tasks also cannot be guaranteed
absent from a model's training data. The new private 20-case set remains the main application evaluation.

**Second choice: ToolSandbox's stateful testing approach.** Its intermediate milestones, tool dependencies and
insufficient-information cases are useful patterns for testing whether clarification precedes action and whether
later actions use current state. Its native assistant domain differs from refunds; use selected ideas first,
rather than undertaking a second full integration before finishing this release.
[Official repository](https://github.com/apple-aiml-research/ToolSandbox).

**Simulator validation matters as much as another benchmark name.** UserProxyBench studies adherence to private
user roles separately from agent reward and reports substantial score changes when only the simulator changes.
This supports independently checking whether our customer invents a side goal, reveals a fact early or ignores
its stopping rule. It does not prove a particular D13/D28 verdict and is not a drop-in replacement evaluator.
[Research paper](https://arxiv.org/abs/2609.38043).

No external benchmark or paid model call was executed for this review. Application code, prompts, policies,
scenarios and historical audit/results artifacts were not changed by this review.
