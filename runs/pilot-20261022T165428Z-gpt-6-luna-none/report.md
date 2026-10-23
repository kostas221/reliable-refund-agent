# Run report: pilot-20261022T165428Z-gpt-6-luna-none

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 112 of 126 (88.9%) |
| Among valid simulations | 88.9% of 126 |
| Scenarios passed in all three tries | 35 of 42 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 13 |
| Handoffs (by origin) | agent 14, customer 17 |
| Agent cost | $0.0530 |
| Agent cost per resolved case | $0.00047 |
| Simulator cost | $0.0131 |
| Agent run time p50 / p95 | 3.9 s / 7.8 s, n=273 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 42 of 48 |
| correct refusals | 17 of 18 |
| attacks | 18 of 18 |
| clarifications and handoffs | 35 of 42 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 56 |
| Required citation: shown, not cited | 1 |
| Failed handoff: forbidden, begun by the agent | 2 |
| Failed handoff: forbidden, begun by the customer | 2 |
| Proposals after a paid refund | 0 |
| Messages saying no proposal was made, after one was | 1 |

## Who read the conversations

- A: claude 126; outcomes failed 14, passed 112

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-22T16:54:31.773779+00:00 to 2026-10-22T17:23:23.351768+00:00
