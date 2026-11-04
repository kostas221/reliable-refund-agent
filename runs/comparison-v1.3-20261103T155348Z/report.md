# Final evaluation report: comparison-v1.3-20261103T155348Z

## Targets (docs/held-out-v1.3/quality-targets.md)

| | Threshold | Measured | Met |
|---|---|---|---|
| No unauthorized or duplicate committed refund, A and B | none | 0 in A, 0 in B | yes |
| Task success, A | at least 85% | 109 of 117 (93.2%; 95% interval 85.5% to 99.1%) | yes |
| pass^3, A | at least 70% | 35 of 39 | yes |

A target met by the measured rate is met for these 39 scenarios; it is not a claim that the true rate lies above the threshold. Zero observed events do not prove zero risk: were the 117 conversations of A independent, 0 events in them would put the rate below 2.6% with 95% confidence; they are not independent (three tries per scenario), so the bound is wider.

## By configuration

| | A | B |
|---|---|---|
| Conversations that succeeded | 109 of 117 (93.2%) | 108 of 117 (92.3%) |
| Among valid simulations | 93.2% of 117 | 93.1% of 116 |
| Scenarios passed in all three tries | 35 of 39 | 33 of 39 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 85 of 117; all three tries 27 of 39 | 90 of 117; all three tries 27 of 39 |
| Unauthorized or duplicate refunds | 0 | 0 |
| Agent attempts refused by the backend | 0 | 0 |
| Handoffs (by origin) | agent 12, customer 6 | agent 12, customer 6 |
| Agent cost | $0.8594 | $2.1803 |
| Agent cost per resolved case | $0.00788 | $0.02019 |
| Simulator cost | $0.0155 | $0.0193 |
| Agent run time p50 / p95 | 4.8 s / 10.1 s, n=267 | 4.5 s / 9.6 s, n=280 |

### Success by group

| Group | A | B |
|---|---|---|
| eligible refunds | 40 of 42 | 41 of 42 |
| correct refusals | 23 of 24 | 22 of 24 |
| attacks | 19 of 24 | 20 of 24 |
| clarifications and handoffs | 27 of 27 | 25 of 27 |

## Comparisons

Paired bootstrap by scenario, 10000 draws, seed 20261019: the difference in the share of tries that succeeded, the other configuration minus A, with its 95% interval, and per scenario how often the other configuration did better, the same or worse. With 39 scenarios the intervals are wide and support no general claim.

| | Difference | 95% interval | Better / same / worse |
|---|---|---|---|
| A/B | -0.9 points | -6.8 to +5.1 | 3 / 32 / 4 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A | B |
|---|---|---|
| Required citation: shown, cited | 229 | 231 |
| Required citation: shown, cited only by the fact line | 3 | 0 |
| Required citation: shown, not cited | 8 | 9 |
| Conversations that failed on required citations alone | 8 | 8 |
| Quality citations (never failed): shown / not shown | 19 / 29 | 27 / 21 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 1 / 0 | 1 / 1 |
| Proposals after a paid refund | 0 | 0 |
| Messages saying no proposal was made, after one was | 0 | 1 |
| Calls held after a question | 0 | 0 |
| Proposals refused, the customer's words do not say which | 0 | 0 |
| Handoffs refused, a yes to no offer in view | 0 | 0 |
| Handoffs refused, other reasons | 0 | 0 |
| Conversations with the selection refused twice or more | 0 | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 10, unneeded questions 0, false refusals 0, of 117 read | premature cards 13, unneeded questions 3, false refusals 0, of 117 read |
| A customer's yes refused | 0 in 0 conversations | 0 in 0 conversations |
| Cards declined or cancelled with the button | 6 in 6 conversations | 14 in 6 conversations |

## Who read the conversations

- A: claude 117; outcomes failed 8, passed 109
- B: claude 117; outcomes failed 8, not_a_test 1, passed 108

## Machine verdicts corrected after the run

- A: 0
- B: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6.1-sol`, from 2026-11-03T15:53:52.070127+00:00 to 2026-11-03T16:56:19.566884+00:00
- B: `claude-sonnet-5-5`, from 2026-11-03T15:54:19.365273+00:00 to 2026-11-03T16:56:45.258807+00:00
