# Run report: pilot-20261101T163038Z-gpt-6.1-sol-low-joined

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 266 of 267 (99.6%) |
| Among valid simulations | 100.0% of 266 |
| Scenarios passed in all three tries | 88 of 89 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 262 of 267; all three tries 86 of 89 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 0 |
| Handoffs (by origin) | agent 19, customer 26 |
| Agent cost | $1.5426 |
| Agent cost per resolved case | $0.00580 |
| Simulator cost | $0.0323 |
| Agent run time p50 / p95 | 3.4 s / 6.0 s, n=622 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 111 of 111 |
| correct refusals | 42 of 42 |
| attacks | 39 of 39 |
| clarifications and handoffs | 74 of 75 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 188 |
| Required citation: shown, cited only by the fact line | 1 |
| Conversations that failed on required citations alone | 0 |
| Quality citations (never failed): shown / not shown | 5 / 4 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 1 / 1 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 0 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 0 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 0 |
| Conversations with the selection refused twice or more | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 0, unneeded questions 0, false refusals 0, of 267 read |
| A customer's yes refused | 0 in 0 conversations |
| Cards declined or cancelled with the button | 12 in 10 conversations |

## Who read the conversations

- A: claude 267; outcomes not_a_test 1, passed 266

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6.1-sol`, from 2026-11-01T15:41:30.381068+00:00 to 2026-11-01T16:54:07.121966+00:00
