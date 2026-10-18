# Development pilot: question, predictions and limits

Written before the pilot runs (plan sections 9, 11 and 12). `refund_agent/evaluation/pilot.py` refuses a paid run
until this file is committed and unchanged; each run's manifest records the commit. After the run, the results are
written next to this file and compared with what is predicted here. A prediction that turns out wrong stays here.

## The question

Can GPT-6 Luna, through the real tools and backend, handle the ten development scenarios, and which reasoning
setting, `low` or `none`, gives the lower cost per correctly resolved case? A case counts as correctly resolved when
the evaluator finds no machine failure and a person reading the conversation finds the pending items satisfied.

## What runs

- The ten development scenarios, once each, in configuration A, for each setting: 20 conversations in all.
- Agent: `gpt-6-luna` with reasoning `low`, then `none`. Simulated customer: `gpt-6-luna`, reasoning `low`, fixed.
- Budget: $1 per setting (the pilot's limit in the plan is $5). The dry run's worst case for one setting is about
  $0.85, assuming every request uses its maximum output.
- Prices assumed (USD per 1M tokens, input / cached input / output): 0.10 / 0.01 / 0.50, to be checked on the day of
  the run and given to the command.

## Predictions

1. **No unauthorized or duplicate committed refund** in any of the 20 conversations. This does not depend on the
   model: configuration A refuses them in the backend.
2. **Machine failures** (at least one failed item): 1 to 3 of 10 with `low`, 2 to 5 of 10 with `none`. The most
   likely ones: D09 (a proposal before asking which shirt), D10 (no handoff, or refused as simply late), D05 (no
   citation of the window section), D02 (a proposal with the bowl only that the agent does not replace).
3. **Cost**: under $0.10 per setting, and under $0.01 per conversation, simulator included.
4. **Simulated customer**: at least one of the 20 conversations shows a fault of the simulated customer when read
   (an invented fact, a fact revealed before it was asked for, or a typed "I confirm").
5. **Requests**: at most 12 agent requests in any conversation; none stopped by the step limit.

## How the results are read

- Every conversation is read in full, and each pending item is marked passed or failed; a conversation stays
  unknown until then. Faults of the simulated customer are counted apart from the agent's.
- The setting is chosen by cost per correctly resolved case, then by success, then by time (plan section 9).
- With ten scenarios and one try each, the numbers are a first look, not an estimate of quality: no interval is
  claimed, and nothing here is tuned on the held-out scenarios, which this pilot does not touch.

## Second pilot: written on 2026-10-14, after the first pilot's results and before this run

### What changes and what runs

- One change since the first pilot: the notice of a staff decision now says that the customer confirmed and that a
  staff member approved (or rejected) the request, because in the first pilot the agent once asked the customer to
  confirm again after an approval (D09, `low`). That gap was ours, in the backend's wording.
- The agent's instructions do not change. The two other failures (no citation at a handoff, D10 `low`; a handoff
  after a plain refusal, D05 `none`) happened once each in 20 conversations; an instruction is added only for a
  failure that comes back.
- The ten development scenarios, three tries each, for `low` and for `none`: 60 conversations. Same simulated
  customer, configuration A, budget $1 per setting.

### Predictions

1. No unauthorized or duplicate committed refund in any of the 60.
2. Tries without a machine failure: 25 to 29 of 30 for each setting. Scenarios without a machine failure in all
   three tries: 7 to 9 of 10 for each setting.
3. D09, asking to confirm again after an approval: at most 1 of the 6 tries of D09.
4. D10 without a citation at the handoff, and D05 handed off after a plain refusal: each comes back in at least 1 of
   its 6 tries. If so, the matching instruction is added before the setting is chosen and checked once more.
5. Cost: under $0.05 per setting.

### How the setting is chosen

By cost per correctly resolved try; if the two are within 10% of each other, by the number of scenarios resolved
in all three tries; if still tied, by the median time per conversation. A try counts as correctly resolved when the
evaluator finds no machine failure and the reading of the conversation passes its pending items.

## Third check: written on 2026-10-14, after the second pilot's results and before this run

### What changes and what runs

- Instructions version 2 (`prompts/agent-v2.md`): one bullet widened, so the agent cites the section whenever it
  tells the customer what a rule requires, because a missing citation came back (3 times in 80 conversations).
- The description of `propose_refund` says that a new eligible proposal replaces an unconfirmed one, because the
  agent twice told the customer it could not combine items into one proposal (D02, `low`).
- Nothing else changes. The ten development scenarios, three tries each, for `low` and for `none`: 60 conversations,
  budget $1 per setting. The setting is chosen on this run, by the rule written for the second pilot.

### Predictions

1. No unauthorized or duplicate committed refund in any of the 60.
2. A missing citation in at most 1 of the 60 tries.
3. D02 failing because items were not combined into one proposal: at most 1 of its 6 tries.
4. 28 to 30 of 30 tries without a machine failure for each setting.
5. `none` still hands off the friend's order of D07 in at least 1 of 3 tries; nothing here targets it.
6. Cost under $0.05 per setting.

## Run before the freeze: written on 2026-10-18, after phases 4 and 5 and before this run

### What changes and what runs

- The agent is unchanged since the third check: `gpt-6-luna` with reasoning `none` (chosen there), instructions
  version 2, the same seven tools.
- What changed around it (phases 4 and 5, `docs/plan.md` change log): `list_my_orders` and `get_my_order` list each
  order's refund requests with their state and receipt (the D10 gap); the agent's messages are stored after each step,
  in one order with the audit events, and `resolves_ambiguity_first` now needs a customer's answer between the agent's
  question and the first proposal; the test actor leaves D02's card for the bowl alone open (`cards.other = "wait"`),
  so the agent's next proposal must replace it, where until 2026-10-15 that card was declined at once; a staff
  decision reaches the agent through a stored notice; the budget counts every attempt; and `execute` checks
  `same_conversation`.
- The ten development scenarios, three tries each, in configuration A: 30 conversations. Simulated customer
  `gpt-6-luna`, reasoning `low`. Budget $1; the dry run's worst case is $2.56, the third check cost $0.0136 per
  setting.
- The twenty held-out scenarios are written and reviewed, but neither run nor frozen. If this run shows a fault in
  the evaluator or in the scenario format, it is fixed in both sets before the freeze; nothing in a held-out file
  changes because of what the agent does here.

### The question

Do the third check's results hold with these changes, and what happens to the three items it left open: D09
proposing before asking (2 of 3 tries with `none`), D02 replacing an open proposal (never measured), and D10 now
that the agent sees the earlier request?

### Predictions

1. No unauthorized or duplicate committed refund in any of the 30.
2. 27 to 30 of 30 tries without a machine failure (the third check: 28; the stricter D09 pre-check can only lower
   it).
3. D09: a proposal before asking in 1 to 3 of its 3 tries, since nothing the agent sees in D09 changed; each such
   try now fails `resolves_ambiguity_first` itself, not only `proposal_with_other_units`.
4. D02: the refund of the bowl and the plate, R$ 104,80, after a new proposal that replaces the open one, in at
   least 2 of its 3 tries.
5. D10: no missing citation in any of its 3 tries.
6. Cost under $0.05.

### How the results are read

- As before, every conversation is read in full by a person before any pending item counts as passed; faults of the
  simulated customer are counted apart from the agent's.
- If D09 proposes before asking in 2 or 3 of 3, the follow-up written on 2026-10-14 applies: the citation line of
  instructions version 2 is taken out and tested on the development set, before the freeze. With 0 or 1 of 3, the
  instructions stay as they are.
- These numbers, with three tries of ten scenarios, are the basis for the quality targets written before the final
  evaluation; no interval is claimed from them.
