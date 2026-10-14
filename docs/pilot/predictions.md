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
