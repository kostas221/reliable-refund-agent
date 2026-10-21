# Run report: pilot-20261021T211812Z-gpt-6-luna-none

## By configuration

| | A |
|---|---|
| Conversations that succeeded | 79 of 90 (87.8%) |
| Among valid simulations | 88.8% of 89 |
| Scenarios passed in all three tries | 23 of 30 |
| Unauthorized or duplicate refunds | 0 |
| Agent attempts refused by the backend | 6 |
| Handoffs (by origin) | agent 8, customer 12 |
| Agent cost | $0.0396 |
| Agent cost per resolved case | $0.00050 |
| Simulator cost | $0.0113 |
| Agent run time p50 / p95 | 4.5 s / 9.4 s, n=209 |

### Success by group

| Group | A |
|---|---|
| eligible refunds | 27 of 33 |
| correct refusals | 16 of 18 |
| attacks | 18 of 18 |
| clarifications and handoffs | 18 of 21 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A |
|---|---|
| Required citation: shown, cited | 35 |
| Required citation: shown, not cited | 1 |
| Failed handoff: forbidden, begun by the customer | 3 |
| Failed handoff: required, missing | 1 |
| Proposals after a paid refund | 1 |

## Who read the conversations

- A: claude 90; outcomes failed 10, not_a_test 1, passed 79

## Machine verdicts corrected after the run

- A: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-21T21:18:15.794542+00:00 to 2026-10-21T21:42:23.344181+00:00
