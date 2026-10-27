# Generalization review after the v1.1 evaluation run

Date: 2026-10-26. Status: evidence review and recommendation, not a new implementation plan or a final evaluation
report. The frozen implementation, policy, scenarios, audit decisions and quality targets are unchanged.

**Historical snapshot.** This review preceded the v1.2 fixes 1-6 and completion of the Claude dialogue audit later
the same day. Its implementation findings and unread-audit counts describe that earlier inspection. The current
assessment is [the v1.2 follow-up review](review-v1.2-follow-up-2026-10-26.md).

## Recommendation

Finish the dialogue audit of the existing run before changing the agent. Then prioritize a general mechanism for
communicating backend decisions with their relevant policy sources. Improve conversation state only for the remaining
verified failures. More instructions for individual examples, more paid repetitions of familiar scenarios, or an
immediate model switch would not address the largest measured failure category.

There are three distinct questions: whether money was handled correctly, whether the customer's case was resolved,
and whether the explanation met the communication contract. Keep the strict overall score, but report these
dimensions separately. A missing required citation remains a failure under the frozen contract; it is not evidence
of an incorrect payment.

## What the saved evidence currently establishes

Source: `runs/final-v1.1-20261026T125831Z`, all 180 saved `result.json` files, and the three `audit-claude.toml` files.
At inspection, all 180 audit entries still have `read = false`, and there is no final report. The counts below are
mechanical checks, not verified task success. Dialogue quality and simulator fidelity remain unresolved.

| Measure | A: Luna, full checks | B: Sol, full checks | C: Luna, lab checks |
|---|---:|---:|---:|
| Saved conversations / scheduled | 60/60 | 60/60 | 60/60 |
| No mechanical failure, audit still pending | 39/60 (65%) | 45/60 (75%) | 39/60 (65%) |
| Scenarios with no mechanical failure in all three trials | 10/20 | 15/20 | 10/20 |
| Conversations with a mechanical failure | 21/60 | 15/60 | 21/60 |
| Conversations failing only a required citation | 17/60 | 9/60 | 19/60 |
| Conversations with another mechanical failure | 4/60 | 6/60 | 2/60 |
| Required citation checks passed | 46/63 | 54/63 | 44/63 |
| Expected financial outcome checks passed | 60/60 | 60/60 | 60/60 |
| Committed refund operations | 27 | 27 | 27 |
| Conversations with an unauthorized or duplicate refund detected | 0/60 | 0/60 | 0/60 |

The financial outcome check compares the exact refunded units and amounts against the scenario and checks agreement
with operations, ledger lines and receipts (`refund_agent/evaluation/evaluator.py`, `_outcome_items`). Some scenarios
correctly require no refund. Thus 180/180 passing financial outcomes does **not** mean 180 refunds: there were 81
committed demo refund operations, including 54 under full checks in A and B and 27 in C.

No provider, system or budget errors are recorded in the 180 results. This does not establish simulator fidelity:
an actor can complete normally while breaking its assigned role. Likewise, pending checks for false claims and data
disclosure prevent a claim that every aspect of safety passed. Zero observed unauthorized or duplicate effects is
valuable finite-sample evidence, not a zero-risk guarantee or proof about a real payment provider. The 180 trials
reuse 20 scenarios and must not be treated as 180 independent real-world cases.

The latest full development batch reported 124/126 successes and 41/42 scenarios successful in all three trials
(`runs/pilot-20261024T120131Z-gpt-6-luna-none`; `docs/pilot/results.md`). A later targeted cancellation-notice repair
passed D28 in 5/5 trials; that is not a new full 126-conversation result. The development score describes familiar
cases. It cannot be substituted for performance on unseen cases.

## What is failing, and what is not yet known

### 1. Policy explanation is the dominant mechanical failure category

For A, 17 of the 21 mechanically failed conversations fail only a citation check. For B, this is 9 of 15. This is
not permission to relabel those conversations as successes: other communication checks still await review.

Examples from already-run traces:

- `A/H26/try1/result.json`: the assessment exposes the deadline, the correct refund completes and a receipt is given,
  but the required `window` source is absent. The eligible assessment supplies the `amount` source.
- `A/H55/try1/result.json`: the returned item is refunded correctly, but the required `return` source is absent.
- `A/H74/try1/result.json`: a proposal invalidated by changed data is replaced and the refund completes, but the
  required `validity` source is absent.

All three scenarios also have citation failures in B in all three trials. The full policy already appears in the
agent prompt. Adding another retrieval system would therefore not address an unavailable-document problem here.

The code has an uneven communication contract:

- `agent/tools.py`, `_citations`: eligible assessments and proposals attach `amount`; they do not carry a general
  record of all relevant successful conditions and lifecycle explanations.
- `execute_refund` and `request_handoff` return useful factual instructions but no uniform policy-source metadata.
- `agent/facts.py`, `fact_line`: deterministic explanatory text covers only historical receipts and selected
  undelivered order statuses. It was deliberately built for those previously observed cases.

These are mechanisms that can explain the pattern, not proof that one particular change will repair all 17 failures.
The audit must distinguish a correct explanation missing its source from a missing explanation, an inaccurate
explanation, or a questionable scenario expectation.

### 2. The remaining failures need separate diagnoses

In A, the other four mechanically failed conversations comprise one clarification failure and three handoff/state
failures. In B, the other six are clarification failures. In C, the other two are handoff/state failures.

For example, `A/H77/try1/result.json` shows a `shop_decided` handoff rejected because the necessary proposal had not
been recorded. A later customer-requested handoff does not satisfy the expected record and origin. This is a
workflow/recovery issue, not a citation problem. In `A/H41/try3/result.json`, the dialogue ends while a shipping
handoff is unresolved; the simulator and stopping behavior need audit before attributing the cause.

H29 and H52 include information-shaped opening questions. Asking whether to prepare a proposal can fail the
`proposes_without_asking` rule even when the refund ultimately completes correctly. Check the entire authored
customer goal and contract before deciding whether that clarification was harmful. Preserve the original score;
any proven evaluator defect requires a documented, versioned correction applied consistently to every configuration.

Code inspection also finds broader limits: graph state stores messages and usage, while selection and handoff
helpers infer intent from words and punctuation. Free, intentionally selected helper probes can expose errors in
negation, product identification and multi-question replies. Such counterexamples demonstrate a limitation; they
are not live error-rate estimates and do not demonstrate an unauthorized payment.

### 3. The new set measures novelty, not normal customer frequency

The protocol explicitly excludes a candidate if it uses the same deciding rule and conversation shape as a
development case (`docs/held-out-v1.1/protocol.md`, section 3). The change log records that 20 cases were retained
from 70 considered candidates. This is a useful challenge to generalization. It is not a random sample of support
traffic, and its score cannot estimate the percentage of ordinary customers the product would satisfy.

The gap from development is consistent with adaptation to familiar cases, different case composition and stricter
coverage of previously unexercised communication requirements. It does not, on its own, establish how much each
cause contributes, or show that the newer implementation regressed against v1 on the same unseen cases.

## Relevant external evidence

- [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents),
  published January 9, 2026: distinguishes capability tests from regression tests and stresses transcript review,
  simulator/task validity and grader calibration. This is engineering experience, not an independent estimate for
  our shop. Application: familiar cases protect existing behavior; separate unseen cases test broader ability.
- [Anthropic: Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents),
  published September 11, 2025: reports improvements from tool design evaluated on held-out internal tasks, and
  recommends meaningful tool results and inspecting failed trajectories. Application: improve the information
  contract between the backend and the agent. Those internal tool results do not predict our improvement size.
- [Fin: Building Fin Procedures](https://fin.ai/help/en/articles/13976254-building-fin-procedures), dated July 30,
  2026: documents explicit steps, major conditional branches, tools, simulations and version history. Application:
  track consequential workflow state explicitly while leaving ordinary wording flexible. This documents a deployed
  product capability; it does not prove Fin performs better on our scenarios.
- [Sierra: tau-bench evaluation documentation](https://github.com/sierra-research/tau2-bench/blob/main/docs/evaluation.md),
  inspected October 26, 2026: distinguishes database outcomes from communication and allows alternative trajectories
  yielding the correct outcome. Application: retain both outcome and communication checks without assuming a single
  reference conversation is the only valid one. The linked main branch can change.

These sources support a development method. None supplies a transferable success percentage or an assurance that
an architectural change will reach our 85% and 70% targets.

## A bounded next step

1. **Close the existing measurement.** Audit all 180 dialogues under the frozen protocol, with the required owner
   review. Publish the strict overall score, financial outcomes, citation-only failures, handoff/clarification
   failures and simulator faults separately. Calculate model comparisons and intervals by scenario only after
   the audit. Do not choose a model from the preliminary 39/60 versus 45/60 counts.
2. **Test one general communication change.** Have trusted backend results carry the facts being explained, the
   relevant policy sections and their scope: which request, units, decision and state they describe. Render a short
   factual explanation from that data, consistently in chat, UI and the evaluation transcript. Keep the language
   model for the conversation. Do not append every policy section to every answer or infer relevance from scenario
   IDs. Pure information questions still need a supported answer; a receipt renderer alone cannot solve them.
3. **Address residual workflow errors only when verified.** If the audit confirms them, represent the pending
   selection or staff offer and its purpose explicitly, so a reply is associated with a particular question. Do
   not treat a question mark or an isolated `yes` as sufficient evidence. Ambiguous language can trigger a short
   clarification. These conversational records grant no payment authority; customer confirmation and staff
   approval remain bound to the exact proposal in the domain service.
4. **Measure transfer with a fixed stopping rule.** Before any paid run, write the hypothesis, predictions, budget
   and acceptance rule; run free end-to-end mocks and read a complete logged prompt. Use development variants across
   lifecycle stages, multiple items, revised intent and different authors to test the mechanism rather than one
   wording. Keep related scenario families together when separating tuning and validation. A future evaluation
   should label representative supported workflows separately from deliberately novel combinations; never silently
   replace the difficult current result with an easier aggregate. Once a test informs a fix, it is no longer fresh
   evidence for that fix.

The first candidate change is about grounded communication, because it targets the largest observed mechanical
failure family. No gain is promised from the 17 citation-only failures: valid-source rendering must also be checked
for false statements, irrelevant sources, stale state and regressions. A later implementation decision must be
recorded in the frozen plan's change log with its measured justification. No paid calls, implementation changes,
scenario edits or audit verdict changes were made for this review.
