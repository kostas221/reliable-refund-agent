# Run report: pilot-20261029T143336Z-gpt-6-luna-none

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 184 of 186 (98.9%) |
| Among valid simulations | 99.5% of 185 |
| Scenarios passed in all three tries | 60 of 62 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 184 of 186; all three tries 60 of 62 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 21 |
| Handoffs (by origin) | agent 21, customer 24 |
| Agent cost | $0.0835 |
| Agent cost per resolved case | $0.00045 |
| Simulator cost | $0.0229 |
| Agent run time p50 / p95 | 3.8 s / 8.1 s, n=423 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 71 of 72 |
| correct refusals | 30 of 30 |
| attacks | 30 of 30 |
| clarifications and handoffs | 53 of 54 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 117 |
| Failed handoff: forbidden, begun by the customer | 2 |
| Conversations that failed on required citations alone | 0 |
| Quality citations (never failed): shown / not shown | 3 / 0 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 1 / 0 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 2 |
| Calls held after a question | 2 |
| Proposals refused, the customer's words do not say which | 9 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 12 |
| Conversations with the selection refused twice or more | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 11, unneeded questions 1, false refusals 3, of 186 read |
| A customer's yes refused | 0 in 0 conversations |
| Cards declined or cancelled with the button | 18 in 15 conversations |

## Who read the conversations

- A: claude 186; outcomes failed 1, not_a_test 1, passed 184

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-29T14:33:42.971094+00:00 to 2026-10-29T15:15:40.233795+00:00
