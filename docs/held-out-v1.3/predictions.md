# Comparison of v1.3: question and predictions

For anyone reading the report of the comparison of v1.3: the question it answers and what Claude expected, written
before any scenario of `scenarios/held-out-v1.3/` has been run by a model. The results are compared with this page in
the results, wrong predictions included. The final runner refuses to start unless this page is committed and
unchanged.

**Status: written by Claude on 2026-11-03**, after the owner approved the 39 scenarios and the set was frozen,
before any of them was run by a model.

## The question

On 39 scenarios written by an author who never saw the project ([protocol.md](protocol.md)), most of them joining two
or more rules in one conversation or changing course in it:

1. Does the product, with its model GPT-6.1 Sol at reasoning `low` (A), meet its [quality targets](quality-targets.md)
   on scenarios harder than any earlier set?
2. Which model resolves more of them, Sol (A) or Claude Sonnet 5.5 at effort `low` (B), and at what cost?
3. Which model does the decision rule recommend for the product?

## What runs

| Configuration | Agent | Checks in `execute_refund` | Conversations |
|---|---|---|---:|
| A | `gpt-6.1-sol`, reasoning `low` | all | 117 |
| B | `claude-sonnet-5-5`, effort `low`, through `agent/anthropic_adapter.py` | all | 117 |

Both run the agent frozen at commit `80c5a0b`: instructions v10, the same tools, graph, backend rules and policy v2.
Since then only the model plumbing changed: the budget's lock and holds, the Anthropic adapter with its cache mark, and
the adapter chosen by model name. The live mode and evaluation files changed too. The simulated customer is
`gpt-6-luna` with reasoning `low` and instructions v2 in both configurations, as decided on 2026-11-02 (plan change
log), and there are no fallbacks.

Each scenario runs three times in each configuration. For each scenario and try, A then B run one after another, so
each compared pair ran under the same conditions. One invocation of the final runner (`--set held_out_v1_3`) runs
both, with one budget.

## How A and B are compared, chosen now

The paired difference of success, B minus A, by scenario, with its 95% bootstrap interval (10,000 draws):

- wholly above zero: "On 39 new scenarios, Sonnet resolved X points more than Sol, at Y times the agent cost per
  resolved case";
- wholly below zero: "On 39 new scenarios, Sol resolved X points more than Sonnet, at 1/Y of the agent cost per
  resolved case";
- otherwise: "On 39 new scenarios no difference between Sonnet and Sol could be shown (X points, 95% interval
  ...)".

What the decision rule then recommends is on [quality-targets.md](quality-targets.md).

## Predictions

1. **Safety:** no unauthorized or duplicate refund in any of the 234 conversations.
2. **Task success in A:** 92 to 110 of 117 (79% to 94%). Whether target 1 (100) is met is about even. Sol resolved
   266 of 267 development conversations and 54 of 57 in v1.2's held-out set, but this set asks for 80 required
   citations with obligations, two or three in 34 of the 39 scenarios.
3. **pass^3 in A:** 25 to 34 of 39. Whether target 2 (28) is met is about even, slightly more likely met than missed.
4. **The main cause of A's failures:** a required citation left out, or its obligation not told. This happens most in
   the seven scenarios with three required sections (H403, H404, H422, H435, H440, H464, H466) and in the five that
   replace an open card (H401, H405, H410, H465, H472), where `approval` must be cited. More than half of A's failed
   conversations fail on citations alone.
5. **B against A:** B resolves between 10 points fewer and 6 more than A, and the 95% interval includes zero. On
   the development set the two were within one conversation of each other. Sonnet runs a prompt developed with
   OpenAI models and meets an OpenAI simulated customer.
6. **The decision rule:** no difference is shown, and Sol stays the product's model.
7. **Required handoffs (6 scenarios, 18 conversations each):** A hands off correctly in at least 16 of 18, and so
   does B. The likeliest misses are H462 (the disputed return comes after a paid refund, in an order with two payment
   records) and H466 (a disputed return and a shipping request together).
8. **Clarification (H469, H471, H472, 9 conversations each):** A asks which item before its first proposal in at
   least 8 of 9 (Sol asked first in 21 of 21 on development), and B in at least 7 of 9.
9. **Behaviour seen in Sonnet on development** recurs at least once in B and never in A:
   - a wrong amount stated in the text, a machine failure of `states_correct_amount`;
   - a card made for the remaining unit where the customer refused a partial refund (H426, H428), which the
     customer then declines. B has more cards declined or cancelled with the button than A.
10. **Cost:** A's agent $0.70 to $1.30, B's agent $1.80 to $3.20, the simulated customer under $0.10. Both together
    stay under $4.50. B costs 2 to 3 times A per conversation, as on development after the cache mark (2.45 times).
    The budget asked for is $6, within the plan's $15.
11. **Run time:** the agent's p95 per turn is at most 10 seconds in A and at most 15 in B.
12. **Unit labels:** the simulated customer names an author's label, such as "u2", in at most 10 of the 234
    conversations.

## How the results are read

- **Every conversation is audited.** Claude reads all 234. The owner reads, without Claude's verdicts, the
  conversations the recorded rule selects (`python -m refund_agent.evaluation.audit sample`). The simulated
  customer's adherence to its role is checked in every conversation and counted apart; a conversation it broke is no
  test of the agent.
- **The report** (`python -m refund_agent.evaluation.report`) gives the targets first, then the measures listed in
  [quality-targets.md](quality-targets.md), and the comparison B against A with its interval.
- **The whole result is published, whatever it is,** with the limits of [quality-targets.md](quality-targets.md).
  Nothing is tuned on these scenarios.
