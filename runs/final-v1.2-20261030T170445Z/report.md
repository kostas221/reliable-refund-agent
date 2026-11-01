# Final evaluation report: final-v1.2-20261030T170445Z

## Targets (docs/held-out-v1.2/quality-targets.md)

| | Threshold | Measured | Met |
|---|---|---|---|
| No unauthorized or duplicate committed refund, A and B | none | 0 in A, 0 in B | yes |
| Task success, A | at least 85% | 50 of 57 (87.7%; 95% interval 71.9% to 100.0%) | yes |
| pass^3, A | at least 70% | 16 of 19 | yes |

A target met by the measured rate is met for these 19 scenarios; it is not a claim that the true rate lies above the threshold. Zero observed events do not prove zero risk: were the 57 conversations of A independent, 0 events in them would put the rate below 5.3% with 95% confidence; they are not independent (three tries per scenario), so the bound is wider.

## By configuration

| | A | B | C |
|---|---|---|---|
| Conversations that succeeded | 50 of 57 (87.7%) | 54 of 57 (94.7%) | 49 of 57 (86.0%) |
| Among valid simulations | 87.7% of 57 | 94.7% of 57 | 86.0% of 57 |
| Scenarios passed in all three tries | 16 of 19 | 18 of 19 | 15 of 19 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 45 of 57; all three tries 14 of 19 | 49 of 57; all three tries 16 of 19 | 44 of 57; all three tries 13 of 19 |
| Unauthorized or duplicate refunds | 0 | 0 | 0 |
| Agent attempts refused by the backend | 0 | 0 | 1 |
| Handoffs (by origin) | 0 | 0 | agent 1 |
| Agent cost | $0.0256 | $0.3534 | $0.0247 |
| Agent cost per resolved case | $0.00051 | $0.00654 | $0.00050 |
| Simulator cost | $0.0066 | $0.0072 | $0.0066 |
| Agent run time p50 / p95 | 3.7 s / 8.3 s, n=126 | 4.5 s / 8.2 s, n=131 | 3.4 s / 7.5 s, n=124 |

### Success by group

| Group | A | B | C |
|---|---|---|---|
| eligible refunds | 29 of 30 | 30 of 30 | 29 of 30 |
| correct refusals | 9 of 12 | 9 of 12 | 8 of 12 |
| attacks | 3 of 3 | 3 of 3 | 3 of 3 |
| clarifications and handoffs | 9 of 12 | 12 of 12 | 9 of 12 |

## Comparisons

Paired bootstrap by scenario, 10000 draws, seed 20261019: the difference in the share of tries that succeeded, the other configuration minus A, with its 95% interval, and per scenario how often the other configuration did better, the same or worse. With 19 scenarios the intervals are wide and support no general claim.

| | Difference | 95% interval | Better / same / worse |
|---|---|---|---|
| A/B | +7.0 points | +0.0 to +19.3 | 2 / 17 / 0 |
| A/C | -1.8 points | -5.3 to +0.0 | 0 / 18 / 1 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A | B | C |
|---|---|---|---|
| Required citation: shown, cited | 62 | 63 | 62 |
| Required citation: shown, not cited | 4 | 3 | 4 |
| Failed handoff: forbidden, begun by the agent | 0 | 0 | 1 |
| Conversations that failed on required citations alone | 1 | 3 | 2 |
| Quality citations (never failed): shown / not shown | 1 / 5 | 1 / 5 | 1 / 5 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 0 / 1 | 1 / 1 | 0 / 0 |
| Proposals after a paid refund | 0 | 0 | 0 |
| Messages saying no proposal was made, after one was | 0 | 0 | 0 |
| Calls held after a question | 0 | 0 | 0 |
| Proposals refused, the customer's words do not say which | 0 | 0 | 0 |
| Handoffs refused, a yes to no offer in view | 0 | 0 | 0 |
| Handoffs refused, other reasons | 0 | 0 | 1 |
| Conversations with the selection refused twice or more | 0 | 0 | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 1, unneeded questions 0, false refusals 0, of 57 read | premature cards 0, unneeded questions 0, false refusals 0, of 57 read | premature cards 2, unneeded questions 0, false refusals 0, of 57 read |
| A customer's yes refused | 0 in 0 conversations | 0 in 0 conversations | 0 in 0 conversations |
| Cards declined or cancelled with the button | 10 in 10 conversations | 6 in 6 conversations | 10 in 9 conversations |

## Who read the conversations

- A: claude 57; outcomes failed 7, passed 50
- B: claude 57; outcomes failed 3, passed 54
- C: claude 57; outcomes failed 8, passed 49

## Machine verdicts corrected after the run

- A: 0
- B: 0
- C: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-30T17:04:47.426115+00:00 to 2026-10-30T17:41:29.507465+00:00
- B: `gpt-6.1-sol`, from 2026-10-30T17:05:04.275039+00:00 to 2026-10-30T17:41:42.279226+00:00
- C: `gpt-6-luna`, from 2026-10-30T17:05:18.007148+00:00 to 2026-10-30T17:41:55.118597+00:00
