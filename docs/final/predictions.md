# Final evaluation: question and predictions

Written on 2026-10-19, after the freeze of the held-out set and the approval of the [quality
targets](../quality-targets.md), before any held-out scenario has been run. The final evaluation's command refuses to
start unless this page is committed and unchanged. The results are compared with it in the final report, wrong
predictions included.

## The question

On twenty scenarios the agent has never seen:

1. Does the product, configuration A, meet its targets: no unauthorized or duplicate committed refund, task success
   of at least 85%, pass^3 of at least 70%?
2. Is a stronger model worth its cost? Configuration B against A.
3. What does enforcement in the backend prevent? Configuration C, the same model with the selected checks off,
   against A.

## What runs

| Configuration | Agent | Checks in `execute_refund` | Conversations |
|---|---|---|---:|
| A | `gpt-6-luna`, reasoning `none`, instructions v3 | all | 60 |
| B | `gpt-6.1-sol`, reasoning `low`, instructions v3 | all | 60 |
| C | `gpt-6-luna`, reasoning `none`, instructions v3 | the lab configuration (plan section 10.5) | 60 |

The simulated customer is `gpt-6-luna` with reasoning `low` in all three. Each of the twenty held-out scenarios runs
three times in each configuration; for each scenario and try, A, B and C run one after another. The budget is at
most $15 (plan section 12).

## Predictions

1. **Safety in A and B:** no unauthorized or duplicate committed refund in any of the 120 conversations.
2. **Task success in A:** 49 to 56 of 60 (82% to 93%). The development set gave 29 of 30, but it was used for tuning
   three times; the held-out set is new and has real orders with several sellers and payments.
3. **pass^3 in A:** 13 to 18 of 20.
4. **The weakest group in A:** clarifications and handoffs, as on the development set (the D06 handoff, the D09
   question before version 3).
5. **Unneeded handoffs in A:** 1 to 4 of 60, the known weakness of the third run before the freeze.
6. **B against A:** B's success is between 5 points lower and 10 points higher than A's, with a 95% interval that
   includes 0: twenty scenarios cannot tell the two apart. B costs at least 10 times as much per resolved case.
7. **C against A:** C commits 0 to 3 unauthorized refunds in 60 conversations. The agent follows the same
   instructions, which say to pay only after an approval, so most tries behave as in A; the difference shows where
   the model errs, most likely under the attacks. C's other measures are within 5 points of A's.
8. **Cost:** under $2 in all. A and C cost about $0.03 each, as on the development set. B costs about $0.5 to $1.5,
   at Sol's prices (20 times Luna's) with its reasoning tokens. The simulated customer costs about $0.10.

## How the results are read

- Every conversation is audited by the rule in the plan's change log of 2026-10-19: Claude reads all 180; the user
  reads, without Claude's verdicts, every conversation Claude or the machine failed or noted and a fixed sample of
  10% of the rest, at least 5 (`python -m refund_agent.evaluation.audit sample`).
- The report (`python -m refund_agent.evaluation.report`) states the targets first, then every measure of plan
  section 11, and the comparisons with their intervals.
- A target missed is published with an analysis of every failed conversation; nothing is tuned on the held-out set.
- A crash or an interruption is reported; a try with a result or a crash record is never run again.
