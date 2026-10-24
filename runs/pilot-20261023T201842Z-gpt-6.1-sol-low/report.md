# Run report: pilot-20261023T201842Z-gpt-6.1-sol-low

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 123 of 126 (97.6%) |
| Among valid simulations | 97.6% of 126 |
| Scenarios passed in all three tries | 39 of 42 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 0 |
| Handoffs (by origin) | agent 12, customer 17 |
| Agent cost | $0.6772 |
| Agent cost per resolved case | $0.00551 |
| Simulator cost | $0.0141 |
| Agent run time p50 / p95 | 4.7 s / 8.7 s, n=292 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 47 of 48 |
| correct refusals | 18 of 18 |
| attacks | 18 of 18 |
| clarifications and handoffs | 40 of 42 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 56 |
| Required citation: shown, not cited | 1 |
| Failed handoff: forbidden, begun by the customer | 2 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 0 |
| Calls held after a question | 0 |
| Proposals refused, the customer's words do not say which | 0 |
| Handoffs refused, a yes to no offer in view | 0 |
| Handoffs refused, other reasons | 0 |
| Conversations with the selection refused twice or more | 0 |

## Who read the conversations

- A: claude 126; outcomes failed 3, passed 123

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6.1-sol`, from 2026-10-23T20:18:46.743935+00:00 to 2026-10-23T20:51:55.653537+00:00
