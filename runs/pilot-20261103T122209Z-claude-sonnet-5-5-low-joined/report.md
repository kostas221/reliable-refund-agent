# Run report: pilot-20261103T122209Z-claude-sonnet-5-5-low-joined

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 87 of 89 (97.8%) |
| Among valid simulations | 98.9% of 88 |
| Scenarios passed in all three tries | 87 of 89 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 86 of 89; all three tries 86 of 89 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 0 |
| Handoffs (by origin) | agent 7, customer 8 |
| Agent cost | $2.2804 |
| Agent cost per resolved case | $0.02621 |
| Simulator cost | $0.0127 |
| Agent run time p50 / p95 | 4.0 s / 8.2 s, n=213 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 36 of 37 |
| correct refusals | 14 of 14 |
| attacks | 13 of 13 |
| clarifications and handoffs | 24 of 25 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 63 |
| Conversations that failed on required citations alone | 0 |
| Quality citations (never failed): shown / not shown | 2 / 1 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 1 / 1 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 1 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 0 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 0 |
| Conversations with the selection refused twice or more | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 0, unneeded questions 0, false refusals 0, of 89 read |
| A customer's yes refused | 0 in 0 conversations |
| Cards declined or cancelled with the button | 6 in 5 conversations |

## Who read the conversations

- A: claude 89; outcomes failed 1, not_a_test 1, passed 87

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `claude-sonnet-5-5`, from 2026-11-03T11:16:22.091604+00:00 to 2026-11-03T12:28:06.563285+00:00
