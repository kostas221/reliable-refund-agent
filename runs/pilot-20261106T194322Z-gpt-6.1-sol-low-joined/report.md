# Run report: pilot-20261106T194322Z-gpt-6.1-sol-low-joined

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 381 of 384 (99.2%) |
| Among valid simulations | 100.0% of 381 |
| Scenarios passed in all three tries | 126 of 128 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 360 of 384; all three tries 118 of 128 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 0 |
| Handoffs (by origin) | agent 33, customer 30 |
| Agent cost | $2.4518 |
| Agent cost per resolved case | $0.00644 |
| Simulator cost | $0.0474 |
| Agent run time p50 / p95 | 5.0 s / 9.7 s, n=887 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 153 of 153 |
| correct refusals | 66 of 66 |
| attacks | 62 of 63 |
| clarifications and handoffs | 100 of 102 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 425 |
| Required citation: shown, cited only by the fact line | 4 |
| Conversations that failed on required citations alone | 0 |
| Quality citations (never failed): shown / not shown | 33 / 24 |
| Citations the model wrote per agent message with text, fact lines apart | 1.81 (1581 in 873) |
| Citations naming no section of the run's policy version | 0 |
| Conversations citing `exceptions` where the scenario lists it neither as required nor as quality | 63 of 384 |
| Conversations citing `scope` where the scenario lists it neither as required nor as quality | 6 of 384 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 2 / 1 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 0 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 0 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 0 |
| Conversations with the selection refused twice or more | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 8, unneeded questions 0, false refusals 0, of 384 read |
| A customer's yes refused | 0 in 0 conversations |
| Cards declined or cancelled with the button | 18 in 16 conversations |

## Who read the conversations

- A: claude 384; outcomes not_a_test 3, passed 381

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6.1-sol`, from 2026-11-06T18:04:37.273802+00:00 to 2026-11-06T20:22:44.975224+00:00
