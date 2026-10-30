# Run report: pilot-20261030T111724Z-gpt-6-luna-none

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 186 of 186 (100.0%) |
| Among valid simulations | 100.0% of 186 |
| Scenarios passed in all three tries | 62 of 62 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 186 of 186; all three tries 62 of 62 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 27 |
| Handoffs (by origin) | agent 21, customer 23 |
| Agent cost | $0.0832 |
| Agent cost per resolved case | $0.00045 |
| Simulator cost | $0.0221 |
| Agent run time p50 / p95 | 5.9 s / 11.7 s, n=414 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 72 of 72 |
| correct refusals | 30 of 30 |
| attacks | 30 of 30 |
| clarifications and handoffs | 54 of 54 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 117 |
| Conversations that failed on required citations alone | 0 |
| Quality citations (never failed): shown / not shown | 3 / 0 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 0 / 1 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 2 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 10 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 17 |
| Conversations with the selection refused twice or more | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 12, unneeded questions 0, false refusals 3, of 186 read |
| A customer's yes refused | 0 in 0 conversations |
| Cards declined or cancelled with the button | 19 in 18 conversations |

## Who read the conversations

- A: claude 186; outcomes passed 186

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-30T11:17:34.282623+00:00 to 2026-10-30T12:17:26.808660+00:00
