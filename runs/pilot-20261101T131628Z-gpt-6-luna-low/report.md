# Run report: pilot-20261101T131628Z-gpt-6-luna-low

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 264 of 267 (98.9%) |
| Among valid simulations | 99.2% of 266 |
| Scenarios passed in all three tries | 86 of 89 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 258 of 267; all three tries 84 of 89 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 2 |
| Handoffs (by origin) | agent 21, customer 24 |
| Agent cost | $0.1234 |
| Agent cost per resolved case | $0.00047 |
| Simulator cost | $0.0310 |
| Agent run time p50 / p95 | 3.2 s / 7.0 s, n=606 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 109 of 111 |
| correct refusals | 42 of 42 |
| attacks | 39 of 39 |
| clarifications and handoffs | 74 of 75 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 187 |
| Required citation: shown, cited only by the fact line | 2 |
| Conversations that failed on required citations alone | 0 |
| Quality citations (never failed): shown / not shown | 3 / 6 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 0 / 0 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 1 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 0 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 2 |
| Conversations with the selection refused twice or more | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 7, unneeded questions 1, false refusals 2, of 267 read |
| A customer's yes refused | 0 in 0 conversations |
| Cards declined or cancelled with the button | 19 in 18 conversations |

## Who read the conversations

- A: claude 267; outcomes failed 2, not_a_test 1, passed 264

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-11-01T13:16:36.427080+00:00 to 2026-11-01T14:09:29.875329+00:00
