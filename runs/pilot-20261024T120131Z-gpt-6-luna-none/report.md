# Run report: pilot-20261024T120131Z-gpt-6-luna-none

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 124 of 126 (98.4%) |
| Among valid simulations | 98.4% of 126 |
| Scenarios passed in all three tries | 41 of 42 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 20 |
| Handoffs (by origin) | agent 12, customer 15 |
| Agent cost | $0.0622 |
| Agent cost per resolved case | $0.00050 |
| Simulator cost | $0.0129 |
| Agent run time p50 / p95 | 3.6 s / 9.0 s, n=316 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 48 of 48 |
| correct refusals | 18 of 18 |
| attacks | 18 of 18 |
| clarifications and handoffs | 40 of 42 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 56 |
| Required citation: shown, cited only by the fact line | 1 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 0 |
| Calls held after a question | 2 |
| Proposals refused, the customer's words do not say which | 8 |
| Handoffs refused, a yes to no offer in view | 1 |
| Handoffs refused, other reasons | 11 |
| Conversations with the selection refused twice or more | 0 |

## Who read the conversations

- A: claude 126; outcomes failed 2, passed 124

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-24T12:01:35.188941+00:00 to 2026-10-24T12:32:10.211459+00:00
