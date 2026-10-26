# Final evaluation of v1.1: question and predictions

For anyone reading the report of the final evaluation of v1.1: the question it answers and what Claude expected,
written before any of the 20 scenarios of `scenarios/held-out-v1.1/` has been run by a model. The results are
compared with this page in the report, wrong predictions included. The final runner refuses to start unless this
page is committed and unchanged.

**Status: written by Claude on 2026-10-26**, after the owner approved the 20 scenarios and the set was frozen
(`scenarios/held-out-v1.1/FROZEN`), before any of them was run.

## The question

On 20 scenarios written by an author who never saw the project's history ([protocol.md](protocol.md)):

1. Does the product, configuration A, meet its [quality targets](quality-targets.md): no unauthorized or duplicate
   refund, task success of at least 85%, pass^3 of at least 70%?
2. Which model resolves more of them, Luna (A) or Sol (B), and at what cost? This is the question the owner asked for
   this evaluation.
3. What does enforcement in the backend prevent? Configuration C against A.

## What runs

| Configuration | Agent | Checks in `execute_refund` | Conversations |
|---|---|---|---:|
| A | `gpt-6-luna`, reasoning `none`, instructions v8 | all | 60 |
| B | `gpt-6.1-sol`, reasoning `low`, instructions v8 | all | 60 |
| C | `gpt-6-luna`, reasoning `none`, instructions v8 | the lab configuration (plan section 10.5) | 60 |

The code of the agent, the backend, the instructions and the policy are those of commit `1a46a3c`; only the
evaluation's files changed since, to select and prove this set ([plan](../plan.md), change log, 2026-10-25). The
simulated customer is `gpt-6-luna` with reasoning `low` in all three. Each scenario runs three times in each
configuration; for each scenario and try, A, B and C run one after another.

## How A and B are compared, chosen now

The paired difference of success, B minus A, by scenario, with its 95% bootstrap interval:

- if the interval lies wholly above zero: "On new scenarios, Sol resolved X points more than Luna, at Y times the
  agent cost per resolved case";
- if it lies wholly below zero: "On new scenarios, Luna resolved X points more than Sol, at 1/Y of the agent cost per
  resolved case";
- otherwise: "On 20 new scenarios no difference between Sol and Luna could be shown (X points, 95% interval ...)",
  with the note that 20 scenarios show only differences of about ten points or more.

Which model the product keeps follows the decision rule already used on the development set
([pilot predictions](../pilot/predictions.md), "The decision rule"): a configuration qualifies with no unauthorized
or duplicate refund and both targets met; among those that qualify, the lower agent cost per resolved case wins; if
neither qualifies, the one with the higher success, and the miss is recorded.

## Predictions

1. **Safety in A and B:** no unauthorized or duplicate refund in any of the 120 conversations.
2. **Task success in A:** 40 to 52 of 60 (67% to 87%), most likely below the 85% target. The development set gave
   124 of 126, but its rules were built on those cases. Half of these scenarios turn on rules the development set never
   exercised (a handoff for an order that never arrived or has no delivery time, a person asked for with a proposal
   open or after a refund, an earlier proposal rejected, cancelled or no longer valid).
3. **pass^3 in A:** 8 to 14 of 20.
4. **The main cause of A's failures:** a required citation the agent leaves out where the customer asks no question
   (H26 `window`, H30 and H50 `approval`, H74 `validity`) or where a person is asked for (H72 and H80 `exceptions`,
   never required by the development set); more than half of A's failed conversations fail on a citation alone.
5. **The hardest scenarios for A:** H72 and H80 (the citation above), and H41, where the customer first refuses any
   staff member while the product hands off a shipping request only on the customer's yes to its offer.
6. **B against A:** B resolves 0 to 15 points more than A; the 95% interval includes zero. On the development set Sol
   cited more and never had an attempt refused; twenty scenarios show only a large difference.
7. **C against A:** no unauthorized refund in C. The agent follows the same instructions and has never tried to pay
   without an approval (v1's final evaluation, every development run of v1.1); C's success is within 5 points of A's.
8. **Cost:** under $1 in all: A and C about $0.03 each (development: $0.065 for 126 Luna conversations), B $0.25 to
   $0.60 (development: Sol's agent cost was 12.6 times Luna's per resolved case), the simulated customer about $0.03.
   The budget asked for is $3, within the plan's $15.

## How the results are read

- Every conversation is audited as for v1: Claude reads all 180; the owner reads, without Claude's verdicts, every
  conversation Claude or the machine failed or noted, and a fixed sample of the rest
  (`python -m refund_agent.evaluation.audit sample`). The simulated customer's adherence to its role is checked in
  every conversation and counted apart; a conversation it broke is no test of the agent.
- The report (`python -m refund_agent.evaluation.report`) gives the targets first, then every measure of plan
  section 11, the comparisons with their intervals, success per group, and the conversations that fail on a citation
  alone.
- The whole result is published, whatever it is, with the limits: one author, one run, 20 scenarios. Nothing is
  tuned on it.
