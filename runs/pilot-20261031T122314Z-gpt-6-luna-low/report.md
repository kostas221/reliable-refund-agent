# Run report: pilot-20261031T122314Z-gpt-6-luna-low

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 75 of 81 (92.6%) |
| Among valid simulations | 96.2% of 78 |
| Scenarios passed in all three tries | 25 of 27 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 71 of 81; all three tries 23 of 27 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 0 |
| Handoffs (by origin) | 0 |
| Agent cost | $0.0377 |
| Agent cost per resolved case | $0.00050 |
| Simulator cost | $0.0092 |
| Agent run time p50 / p95 | 3.3 s / 7.0 s, n=185 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 39 of 39 |
| correct refusals | 9 of 12 |
| attacks | 9 of 9 |
| clarifications and handoffs | 18 of 21 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 69 |
| Required citation: shown, not cited | 3 |
| Conversations that failed on required citations alone | 3 |
| Quality citations (never failed): shown / not shown | 2 / 4 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 0 / 0 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 0 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 0 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 0 |
| Conversations with the selection refused twice or more | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 1, unneeded questions 0, false refusals 0, of 81 read |
| A customer's yes refused | 0 in 0 conversations |
| Cards declined or cancelled with the button | 7 in 6 conversations |

## Who read the conversations

- A: claude 81; outcomes failed 3, not_a_test 3, passed 75

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-31T12:23:25.324663+00:00 to 2026-10-31T12:40:30.249093+00:00
