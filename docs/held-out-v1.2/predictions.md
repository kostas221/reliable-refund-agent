# Final evaluation of v1.2: question and predictions

For anyone reading the report of the final evaluation of v1.2: the question it answers and what Claude expected,
written before any scenario of `scenarios/held-out-v1.2/` or `scenarios/stress-v1.2/` has been run by a model. The
results are compared with this page in the report, wrong predictions included. The final runner refuses to start
unless this page is committed and unchanged.

**Status: written by Claude on 2026-10-30**, after the owner approved the 27 scenarios and both sets were frozen,
before any of them was run.

## The question

On 19 scenarios written by an author who never saw the project's history ([protocol.md](protocol.md)):

1. Do the changes of v1.2, measured on development scenarios, carry over: does configuration A meet its
   [quality targets](quality-targets.md)?
2. Which model resolves more of them, Luna (A) or Sol (B), and at what cost; and which does the decision rule choose?
3. What does enforcement in the backend prevent? Configuration C against A.

And, apart, on 8 stress scenarios Claude wrote: which of four situations no other set holds are weaknesses of the
frozen system?

## What runs

| Configuration | Agent | Checks in `execute_refund` | Held-out | Stress |
|---|---|---|---:|---:|
| A | `gpt-6-luna`, reasoning `none`, instructions v9 | all | 57 | 24 |
| B | `gpt-6.1-sol`, reasoning `low`, instructions v9 | all | 57 | 24 |
| C | `gpt-6-luna`, reasoning `none`, instructions v9 | the lab configuration (plan section 10.5) | 57 | 24 |

The agent, backend, instructions, policy and simulated customer are those of commit `829f6ec`; only evaluation files
changed since, to select and prove these sets (plan change log, 2026-10-30). The simulated customer is `gpt-6-luna`
with reasoning `low` in all three. Each scenario runs three times in each configuration; for each scenario and try, A,
B and C run one after another. The two sets run as two invocations of the final runner, each with its own budget.

## How A and B are compared, chosen now

The paired difference of success, B minus A, by scenario, with its 95% bootstrap interval:

- wholly above zero: "On 19 new scenarios, Sol resolved X points more than Luna, at Y times the agent cost per
  resolved case";
- wholly below zero: "On 19 new scenarios, Luna resolved X points more than Sol, at 1/Y of the agent cost per resolved
  case";
- otherwise: "On 19 new scenarios no difference between Sol and Luna could be shown (X points, 95% interval ...)",
  with the note that 19 scenarios show only differences of about ten points or more.

## Predictions

1. **Safety in A and B:** no unauthorized or duplicate refund in any of the 162 conversations of both sets.
2. **Task success in A:** 42 to 53 of 57 (74% to 93%); whether target 1 (49) is met is about even. The development set
   gave 186 of 186, but its rules were built on those cases; these join two situations in one conversation, and 15 of
   the 19 require a citation in an answer to a question asked beside the request or for a second refused unit.
3. **pass^3 in A:** 11 to 16 of 19; target 2 (14) is more likely missed than met, since a few failures spread over
   several scenarios.
4. **The main cause of A's failures:** a required citation left out, in the scenarios with two required sections
   (H233, H241, H255, H261, H314) or a section that answers a question asked beside the request (H108, H113, H235,
   H238, H240, H245, H281, H286, H300, H355). More than half of A's failed conversations fail on a citation alone.
5. **The scenarios hardest for A:** H300 (a change of units on an open card, then a rejection: `approval` is easily
   left out), H233 and H241 (eight and ten hours before the deadline, with a second question: a date error or one of the
   two sections left out), and H255 and H314 (two refusals, each with its section).
6. **B against A:** B resolves 0 to 12 points more than A; the 95% interval includes zero. On the development set Sol
   cited more and never had an attempt refused.
7. **The decision rule:** most likely neither A nor B meets both targets, and the rule then chooses the one with the
   higher success, most likely B, with the miss recorded; if both qualify, A, at the lower cost.
8. **C against A:** no unauthorized refund in C; the agent follows the same instructions and has never tried to pay
   without an approval. C's success is within 5 points of A's.
9. **Stress set, A:** 14 to 21 of 24 conversations pass. The likeliest failures: S05 and S06 (the agent refuses because
   the customer's detail does not match, instead of proposing or asking), S01 and S02 (`remaining` or `payment` left out
   after the receipt), and S04 (a handoff attempted on the withdrawn request, which the backend's rule refuses, so it
   costs a process fault rather than a failure).
10. **Cost:** under $1.50 for both sets together (v1.1's final run cost $0.57 for 180 conversations; these are 243),
    most of it B. The budgets asked for are $5 for each invocation, within the plan's $15.

## How the results are read

- Every conversation is audited: Claude reads all 243; the owner reads, without Claude's verdicts, the conversations
  the recorded rule selects (`python -m refund_agent.evaluation.audit sample`). The simulated customer's adherence to
  its role is checked in every conversation and counted apart; a conversation it broke is no test of the agent.
- The report (`python -m refund_agent.evaluation.report`) gives the targets first, then the measures listed in
  [quality-targets.md](quality-targets.md), the comparisons with their intervals, and the stress set apart.
- The whole result is published, whatever it is, with the limits of [quality-targets.md](quality-targets.md). Nothing
  is tuned on these scenarios; a failure of the stress set becomes a development scenario of v1.3.
