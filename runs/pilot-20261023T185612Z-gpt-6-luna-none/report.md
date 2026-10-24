# Run report: pilot-20261023T185612Z-gpt-6-luna-none

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 120 of 126 (95.2%) |
| Among valid simulations | 95.2% of 126 |
| Scenarios passed in all three tries | 39 of 42 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 20 |
| Handoffs (by origin) | agent 15, customer 16 |
| Agent cost | $0.0523 |
| Agent cost per resolved case | $0.00044 |
| Simulator cost | $0.0127 |
| Agent run time p50 / p95 | 9.4 s / 26.3 s, n=271 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 45 of 48 |
| correct refusals | 16 of 18 |
| attacks | 18 of 18 |
| clarifications and handoffs | 41 of 42 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 54 |
| Required citation: shown, not cited | 3 |
| Failed handoff: forbidden, begun by the agent | 3 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 3 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 10 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 10 |
| Conversations with the selection refused twice or more | 0 |

## Who read the conversations

- A: claude 126; outcomes failed 6, passed 120

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-23T18:56:15.984360+00:00 to 2026-10-23T19:58:24.924035+00:00
