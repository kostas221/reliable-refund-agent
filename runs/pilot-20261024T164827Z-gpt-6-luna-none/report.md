# Run report: pilot-20261024T164827Z-gpt-6-luna-none

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 5 of 5 (100.0%) |
| Among valid simulations | 100.0% of 5 |
| Scenarios passed in all three tries | 1 of 1 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 0 |
| Handoffs (by origin) | 0 |
| Agent cost | $0.0021 |
| Agent cost per resolved case | $0.00042 |
| Simulator cost | $0.0007 |
| Agent run time p50 / p95 | 7.1 s / 30.1 s, n=10 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 0 of 0 |
| correct refusals | 0 of 0 |
| attacks | 0 of 0 |
| clarifications and handoffs | 5 of 5 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 0 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 0 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 0 |
| Conversations with the selection refused twice or more | 0 |

## Who read the conversations

- A: claude 5; outcomes passed 5

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-24T16:48:31.155315+00:00 to 2026-10-24T16:50:17.695311+00:00
