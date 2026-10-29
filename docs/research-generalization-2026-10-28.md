# Generalization review after the v1.2 development confirmation

Reviewed on 2026-10-27 and 2026-10-28. This is an advisory review, not a change to the frozen plan or system.

## Recommendation

Complete the reserved independent evaluation of commit `795d430`, with its known limitations disclosed. The next
implementation priority should be explicit conversational state and current, entity-bound facts. This addresses
several failure mechanisms with one coherent change: losing the offer a customer accepted, confusing a mention
with a selection, and announcing a historical record as if it were current.

Do not start another round of tuning on the same 62 scenarios merely to maintain 100%. Do not migrate frameworks
or add agents, fine-tuning, retrieval, or longer instructions without a measured need. The existing transactional
authority, confirmation, staff approval, and at-most-once execution remain the foundation.

The project is viable as the defined, bounded v1 demonstration. Generalization to unseen simulated conversations
is still unmeasured for this version, and reliability with real customers is a further, separate question.

## What the current result establishes

Evidence: `docs/pilot/results.md`, section "v1.2 confirmation on development (step C)", and
`runs/pilot-20261027T144002Z-gpt-6-luna-none/`. System commit `795d430`, fingerprint
`96e452ab42f2267ab1ce14f1b8b72f6a22b4685a5d437e3b168eed240efad778`.

| Observation | Denominator and interpretation |
|---|---|
| 186/186 conversations passed | 62 known development scenarios, three attempts each. This is regression evidence, not an estimate of success on unseen tasks. |
| 62/62 passed all three attempts | The scenario-level consistency measure, pass^3, on that same development set. |
| No unauthorized or duplicate refund observed | 0 in 186 conversations. This does not mean zero risk in an arbitrary future workload; not every conversation is a payment opportunity. |
| Both citation-rule views passed | 186/186 under the current rule and the historical v1.1 citation-presence view. This result cannot be explained simply by relaxing citation requirements. |
| Required citation obligations satisfied | 117/117 according to the recorded audit; 116 citations from the model and one from the automatic fact line. |
| Refused tool attempts | 36 attempts: 10 proposals and 26 handoffs. These are attempts, not necessarily 36 distinct conversations and not 36 unsafe payments. Some refusals correctly enforce policy; others expose avoidable friction. |
| Alternative proposed before the customer wanted it | 15/21 relevant conversations, across seven scenarios, violated the intended "words before proposal" sequence. This was not a frozen success criterion. |
| Simulator reminder branch | Triggered in 0/186; the live run did not exercise that branch. |
| Audit | Claude read 186/186; owner review remains a distinct source of evidence. Model review is not independent human review. |

All 62 scenarios were available during development. Repeated attempts within a scenario are related, and the
scenarios were not sampled from a production population. An ordinary confidence interval around 186/186 would
not repair that selection bias. The documented historical improvements also combine product, simulator, fixture,
and measurement changes; they do not isolate the effect of the product alone.

The current protocol already provides 40 new independently authored scenarios, fixed group counts, three attempts,
paired comparisons by scenario, a novel subset, and publication of misses. Preserve those improvements.

## Findings in the current implementation

### 1. Dialogue intent is reconstructed from words instead of retained as a bounded interaction

Evidence: `refund_agent/agent/graph.py` (`State`, `_mirror`), `refund_agent/refunds.py` (handoff consent),
and `refund_agent/selection.py` (`_named_at`, `_selected`, `look_alikes_unnamed`).

The financial state is explicit in the domain layer. The conversation graph primarily carries messages and usage;
several dialogue checks reconstruct what the customer means from neighboring text, phrase patterns, and punctuation.

The current run already records:

- One conversation out of 186 where an automatic fact line followed a staff offer. The customer's genuine yes was
  matched against the fact line rather than the offer, causing a refusal and two additional turns.
- Staff offers expressed in legitimate paraphrases that the consent rule did not recognize.
- Direct requests for staff concerning shipping that still require another offer and another yes by design.

The fact-line marker is not retained when `_mirror` writes the message to the SQL conversation. Therefore, even the
small repair "skip fact lines" needs retained message provenance or a turn/offer association. Matching the wording
of generated fact lines would repeat the same fragility elsewhere.

Two additional, deliberately selected helper counterexamples were independently reproduced during this review:

| Customer message and attempted selection | Current helper behavior | Why it matters |
|---|---|---|
| "My rust scarf is fine. Please refund the olive one." Attempt to propose the rust unit. | The language check permits the rust selection. | Mentioning a variant positively is treated as selecting it, even though the request targets the other variant. |
| "Please refund item u1." Attempt to propose unit `u1`, among two look-alike variants. | The language check refuses the selection. | The exact unit ID is not one of the recognized discriminators. |

These probes test the language helper only. They do not demonstrate an actual model choosing the wrong item, an
end-to-end wrong proposal, a bypass of confirmation/staff approval, or a wrong committed payment. They establish
that the helper is not a general semantic validator. The second case is a supported-input limitation rather than
evidence that customers routinely use unit IDs.

**Recommended next mechanism:** retain the purpose and target of the pending interaction. For example:

```text
pending interaction:
  kind: accept_staff_offer
  subject: shipping_charge
  order_id: o1
  offered_in_turn: t12
  status: awaiting_customer
```

This is illustrative, not a proposed schema migration. The existing graph can retain the conversational context;
any durable handoff/approval transition still belongs to the domain services. The customer response should resolve,
reject, or supersede this interaction. An informational line must not silently replace it. A question about item
selection similarly carries the actual candidate IDs and the relevant customer message, rather than only the
assistant's wording.

Let the model interpret free language into a constrained proposed interpretation; validate IDs, actor, ownership,
state, and allowed actions in code. A valid structured output does not prove semantic correctness. Ambiguous
interpretations still need clarification, and consequential actions still need the existing confirmations.
Do not replace transactional authority with a model's claim that consent exists.

### 2. The fact line can assert a stale record as a current fact

**New verified helper bug**, not an observed failure in the 186 conversations.

In `refund_agent/agent/facts.py`, `_tool_facts` adds non-delivered order statuses to `on_its_way`. A later read of
the same order with status `delivered` does not remove the earlier status. `fact_line` then uses the presence of a
status word in the answer to decide whether to emit a sentence.

Reproduction:

1. A tool returns order `o1` as `shipped`.
2. A later tool returns the same order as `delivered`.
3. The answer says: "The previous record said shipped, but the latest record now says delivered."
4. The automatic line says: "Only orders recorded as delivered can be refunded through this process, and order o1
   is shipped (refund-policy/v2/eligible-orders)."

The appended claim is false relative to the latest supplied record. A correct policy reference does not make the
associated factual claim correct. The probe does not establish the frequency or reachability of this exact sequence
under the current UI/data-update paths, and it does not show a financial authorization defect.

**Recommended correction in the next repair cycle:** maintain the latest valid observation per entity and bind
generated factual statements to that observation, its source, and the entity it describes. New authoritative state
supersedes old state. Missing, failed, or partial responses must not silently overwrite a valid snapshot. A mere
word match somewhere in the answer is insufficient evidence of which entity or time the answer refers to.

This has stronger justification than another prompt instruction: it is a reproduced deterministic defect.

### 3. Completion and interaction quality need separate evidence

The recorded 15/21 premature alternative proposals show an instruction that the agent often does not follow.
The resulting card can still be declined, and the eventual payment can still be correct. Preserve the 186/186
score under its frozen definition while reporting this process weakness explicitly.

For a future version, define whether this sequence is a required product behavior or a quality preference. If it
is required, specify the observable sequence and its applicable cases before measurement. Do not impose another
brittle natural-language gate merely because an instruction was missed.

Useful separate diagnostics, with their own denominators:

- Correct completion and correct refusal/handoff by scenario group.
- Conversations containing an avoidable refused call, and refused attempts per relevant tool attempt.
- Premature alternative proposals per conversation where an alternative needs acceptance.
- Unnecessary clarification or repeated consent requests per applicable interaction.
- Recovery turns, and episodes that repeat the same refusal without new information.
- Unsupported or stale factual claims, distinct from citation presence.

Review refusal reasons before trying to lower their count. Reducing correct safety refusals would make the metric
look better while making the product worse. Do not reward handing every difficult case to staff: a handoff is a
success only when it is an acceptable outcome for that task.

## What external systems and research support

Sources were checked on 2026-10-27/28. Product documentation establishes a described mechanism, not independent
superiority over this project. Research results concern their own models, tasks, and evaluators; none supplies a
promised percentage gain for Refund.

| Primary source | Evidence and limitation | Application here |
|---|---|---|
| [Salesforce Architects: Hybrid Reasoning](https://architect.salesforce.com/docs/architect/fundamentals/guide/hybrid-reasoning-agentforce-builder-agent-script.html), documentation, no stable publication date shown | Describes stored execution state, code-controlled transitions and guards, with model reasoning at selected nodes. This is architecture documentation, not a controlled comparison. | Retain explicit pending interactions inside the existing architecture; no need to adopt Agentforce. |
| [Rasa: Dialogue Understanding](https://rasa.com/docs/learn/concepts/dialogue-understanding), documentation | Describes interpreting conversation into structured commands that a dialogue manager applies to flows. The schema does not itself guarantee correct interpretation. | Separate understanding the customer's words from executing an allowed state transition. |
| [Fin: Run simulations for Procedures](https://fin.ai/help/en/articles/13976191-run-simulations-for-fin-procedures), documentation | Tests paths, backend failures, and facts revealed later. Its simulations bypass procedure intent matching and do not call real external systems. | Distinguish understanding the request, completing the conversation, and correctly executing the transaction. Passing one layer does not prove all layers. |
| [Gorgias: Create an Action](https://docs.gorgias.com/en-US/create-an-action-for-ai-agent-567325), documentation | Actions use conditions, ordered steps, and customer confirmation when configured. No comparable generalization rate is supplied. | Refund already requires customer confirmation and staff approval for every refund; retain those requirements. |
| [Gorgias: Advanced Action options](https://docs.gorgias.com/en-US/create-actions-use-advanced-options-to-build-custom-actions-for-ai-agent-1060364), documentation | Named API outputs become variables for later steps and branches, with descriptions for the model. | Reuse Refund's existing structured tool outputs, retaining their association with the correct entity and current observation. Add fields only for demonstrated gaps; do not rebuild the tool contracts. |
| [Sierra: Agent Development Life Cycle](https://sierra.ai/blog/agent-development-life-cycle), 2024-06-03 | Describes composable skills, constraints, immutable versions, and regression tests from failures. Vendor engineering account. | Supports the existing freeze and regression suite; does not justify endless tuning on it. |
| [Sierra: Simulations](https://sierra.ai/blog/simulations-the-secret-behind-every-great-agent), 2025-08-19 | Describes varied simulated customers and outcome/process/quality evaluation. Reported business figures are vendor claims with different denominators. | Vary style, disclosure order, and changes of mind while keeping the v1 domain fixed. Do not compare vendor resolution percentages directly with our benchmark. |
| [Mind the Sim2Real Gap](https://arxiv.org/abs/2603.11245), COLM 2026, revised 2026-07-31 | Study of 451 people, 165 tasks, and 31 simulators finds simulated users overly cooperative and uniform; stronger general models are not necessarily more faithful simulators. | Add a small qualitative human trial before real-world claims. It can uncover failures, not estimate a dependable production success rate. |
| [How Strongly Should Task State Influence an LLM Agent?](https://arxiv.org/abs/2609.25686), preprint, 2026-09-22 | Controlled comparisons find state enforcement useful for state-decidable constraints, but a flawed linguistic cue detector can reduce performance. Recent preprint, not a universal result. | Keep hard financial guards. Avoid extending word-based consent/intent gates as the main generalization strategy. |
| [ToolRobustBench](https://arxiv.org/abs/2608.23635), preprint, 2026-08 | Tests 15,456 cases, seven models, 16 tools, and 14 perturbation types. Combined perturbations can behave differently from isolated ones. | Test a compact matrix of meaningful variations and combinations rather than accumulating unrelated anecdotes. |
| [Beyond Task Completion: Procedure-Aware Evaluation](https://arxiv.org/abs/2603.03116), preprint, 2026-03-03 | Separates utility, efficiency, interaction quality, and procedural integrity; endpoint success can conceal process failures. Its rates do not transfer to Refund. | Report the 15/21 process issue alongside successful final outcomes. |
| [tau-bench 2.0 README](https://github.com/sierra-research/tau2-bench/blob/main/README.md#comparing-with-v101), current repository documentation | Explicitly says 2.0 scores are not comparable with 1.x after task, simulator, judge, and input changes. | Preserve evaluator versions and historical views; do not attribute combined measurement/product gains to the agent alone. |

LinkedIn was also searched. The [official Sierra post](https://www.linkedin.com/posts/sierra_simulations-the-secret-behind-every-great-activity-7363634945820430340-cJ4_)
links to its simulations article; the [Intercom Procedures and Simulations announcement](https://www.linkedin.com/posts/intercom_ai-is-now-widely-adopted-in-customer-support-activity-7426985959168163840-MejF)
points toward the same workflow/testing approach. These are useful discovery sources, not independent evidence of
superior accuracy. Their underlying technical documentation carries more weight than engagement or promotional
percentages.

## Bounded testing approach for the next development cycle

This is not a replacement for, or an addition to, the reserved hidden set. Do not give these probes or current
failure details to its independent author. Use them as known development evidence after that evaluation.

| Dimension | Example variation | Property to check |
|---|---|---|
| Equivalent wording | "Yes, please" versus a natural paraphrase accepting the same staff offer | The same pending offer is resolved, unless the new wording is genuinely ambiguous. |
| Mention versus request | One item is described as fine; a different item is requested for refund | A mention alone does not select an item. |
| Intervening information | Insert an automatic policy/fact message after an offer | The pending interaction remains associated with the customer response. |
| Changed intent | Customer first selects both items, then explicitly keeps one | The current request supersedes the old selection; do not preserve the old expected outcome. |
| Freshness | Read the same order before and after a valid status update | Statements use the latest authoritative record for that order. |
| Entity separation | Two orders share a status word but only one is being discussed | Evidence and announcements stay bound to the relevant order. |
| Refusal and recovery | A declined card, then a materially different request | The declined request stays declined; the new request is interpreted on its own merits. |
| Supported failure combinations | A pending interaction plus a harmless extra detail or a recoverable tool failure | Context survives and recovery does not repeat an invalid action without new information. |

These are relations between cases, not a demand to enumerate every sentence. When meaning is preserved, the
acceptable result should remain equivalent. When the customer changes intent or records change, the expected
result must change accordingly.

Pure helpers, state transitions, and mocked end-to-end paths can be tested for free. Such tests do not prove that
the live model interprets every paraphrase correctly. A bounded live test must still be run by the user with
written predictions, the logged prompt reviewed, and a budget cap. No paid runs were performed for this review.

Do not build a new universal model judge as a prerequisite. Use existing traces, scenario assertions, and focused
manual review first. A reviewer should distinguish a valid safety refusal from a false refusal, and a correct
handoff from an unnecessary one.

## Order of work and release implications

1. **Preserve the current comparison.** Complete the existing independent 40-scenario protocol for the frozen
   version. Record the newly found helper limitations as known before the evaluation, without changing its hidden
   cases to target them. Keep safety, completion, pass^3, group results, and novel-subset results separate. Repeated
   attempts do not turn 40 independent tasks into 120 or 360 independent tasks.
2. **Use the resulting failures to choose a bounded repair cycle.** The stale-fact defect already has a direct
   reproduction and should be corrected before calling a later release free of known factual defects. Retaining
   message provenance/pending interactions is the strongest next generalization investment if the observed
   dialogue problems remain material. This can be implemented incrementally in the existing architecture.
3. **Measure the behavioral change under a declared new version.** Retain the old report, test the known cases for
   regression, and use fresh independent cases for any new claim about unseen scenarios. If data interpretation
   improves only with the reference model, use the already planned quality-then-cost model selection; a model
   switch does not repair stale state or a false deterministic validator.
4. **Finish the planned product evidence.** Have a few people try the English flow with their own phrasing, record
   confusion and recovery, and complete the reproducible demo, documentation, and presentation. Three to five
   participants would be a practical qualitative check, not a statistical reliability claim or a new benchmark.

The existing stopping rule reopens work for a safety defect or a correctness regression caused by this bundle.
The probes here establish neither an unauthorized payment nor a newly introduced regression. Keeping the current
freeze is therefore the recommended scheduling decision, not a claim that known defects are acceptable forever.
If a repair is deliberately brought forward before the hidden evaluation, a new documented freeze is possible;
silently changing the frozen implementation is not. This review does not make that decision or change the plan.

No evidence found justifies a general promise of 100% on new scenarios. A defensible v1 demonstrates correct
authorization and execution, honestly measured conversational limitations, recovery or staff escalation where
appropriate, and a reproducible process for improving observed failure classes.

## Reproducible local probes

Executed against the current source with the local Python environment. No model API, database connection, or
secret file was used. These assertions confirm current defects/limitations; they are not acceptance tests for a
corrected implementation and were not added to the product's test suite.

```python
import json
from datetime import date

from refund_agent.agent.facts import fact_line
from refund_agent.policy import load_policy
from refund_agent.selection import Kind, look_alikes_unnamed

history = [
    {
        "role": "tool",
        "name": "get_my_order",
        "content": json.dumps({"ok": True, "order": {"order_id": "o1", "status": status}}),
    }
    for status in ("shipped", "delivered")
]
answer = "The previous record said shipped, but the latest record now says delivered."
assert "order o1 is shipped" in fact_line(history, answer, load_policy())

kinds = [
    Kind("o1", "Linen scarf, olive", date(2026, 10, 1), date(2026, 10, 4), ("u1",)),
    Kind("o1", "Linen scarf, rust", date(2026, 10, 1), date(2026, 10, 4), ("u2",)),
]
messages = [("customer", "My rust scarf is fine. Please refund the olive one.")]
assert not look_alikes_unnamed(kinds, ["u2"], messages)
assert look_alikes_unnamed(kinds, ["u1"], [("customer", "Please refund item u1.")])
```

Only this review document was added by the current review. No implementation, evaluator, hidden scenario,
frozen plan, or existing run artifact was changed; no commit or push was made.
