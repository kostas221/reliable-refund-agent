# Run report: pilot-20261023T144102Z-gpt-6-luna-none

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 118 of 126 (93.7%) |
| Among valid simulations | 94.4% of 125 |
| Scenarios passed in all three tries | 37 of 42 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 22 |
| Handoffs (by origin) | agent 15, customer 16 |
| Agent cost | $0.0528 |
| Agent cost per resolved case | $0.00045 |
| Simulator cost | $0.0135 |
| Agent run time p50 / p95 | 5.1 s / 11.7 s, n=274 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 42 of 48 |
| correct refusals | 16 of 18 |
| attacks | 18 of 18 |
| clarifications and handoffs | 42 of 42 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 54 |
| Required citation: shown, not cited | 2 |
| Failed handoff: forbidden, begun by the agent | 3 |
| Failed handoff: forbidden, begun by the customer | 1 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 1 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 9 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 13 |
| Conversations with the selection refused twice or more | 0 |

## Who read the conversations

- A: claude 125, none 1; outcomes failed 7, missing 1, passed 118

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-23T14:41:04.624075+00:00 to 2026-10-23T15:17:07.366991+00:00
