# Run report: pilot-20261020T170431Z-gpt-6-luna-none

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 77 of 90 (85.6%) |
| Among valid simulations | 87.5% of 88 |
| Scenarios passed in all three tries | 23 of 30 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 2 |
| Handoffs (by origin) | agent 9, customer 13 |
| Agent cost | $0.0384 |
| Agent cost per resolved case | $0.00050 |
| Simulator cost | $0.0103 |
| Agent run time p50 / p95 | 8.8 s / 27.9 s, n=200 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 28 of 33 |
| correct refusals | 16 of 18 |
| attacks | 17 of 18 |
| clarifications and handoffs | 16 of 21 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 35 |
| Required citation: shown, not cited | 1 |
| Failed handoff: forbidden, begun by the customer | 4 |
| Proposals after a paid refund | 0 |

## Who read the conversations

- A: claude 90; outcomes failed 11, not_a_test 2, passed 77

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-20T17:04:33.508388+00:00 to 2026-10-20T17:48:36.742696+00:00
