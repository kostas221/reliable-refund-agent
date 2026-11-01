# Run report: pilot-20261031T183540Z-gpt-6-luna-low

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 261 of 267 (97.8%) |
| Among valid simulations | 98.5% of 265 |
| Scenarios passed in all three tries | 85 of 89 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 257 of 267; all three tries 83 of 89 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 3 |
| Handoffs (by origin) | agent 21, customer 22 |
| Agent cost | $0.1244 |
| Agent cost per resolved case | $0.00048 |
| Simulator cost | $0.0316 |
| Agent run time p50 / p95 | 3.2 s / 6.8 s, n=611 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 109 of 111 |
| correct refusals | 42 of 42 |
| attacks | 39 of 39 |
| clarifications and handoffs | 71 of 75 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 184 |
| Required citation: shown, cited only by the fact line | 1 |
| Required citation: shown, not cited | 4 |
| Conversations that failed on required citations alone | 4 |
| Quality citations (never failed): shown / not shown | 5 / 4 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 0 / 1 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 0 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 0 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 3 |
| Conversations with the selection refused twice or more | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 8, unneeded questions 0, false refusals 2, of 267 read |
| A customer's yes refused | 0 in 0 conversations |
| Cards declined or cancelled with the button | 26 in 19 conversations |

## Who read the conversations

- A: claude 267; outcomes failed 4, not_a_test 2, passed 261

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-31T18:35:44.279436+00:00 to 2026-10-31T19:29:43.611615+00:00
