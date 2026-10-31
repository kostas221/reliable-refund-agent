# Final evaluation report: stress-v1.2-20261030T174734Z

No quality target: stress_v1_2 is reported apart (docs/held-out-v1.2/quality-targets.md).

## By configuration

| | A | B | C |
|---|---|---|---|
| Conversations that succeeded | 23 of 24 (95.8%) | 23 of 24 (95.8%) | 23 of 24 (95.8%) |
| Among valid simulations | 100.0% of 23 | 100.0% of 23 | 100.0% of 23 |
| Scenarios passed in all three tries | 7 of 8 | 7 of 8 | 7 of 8 |
| Success under the v1.1 citation rule (every listed citation by its presence alone) | 23 of 24; all three tries 7 of 8 | 23 of 24; all three tries 7 of 8 | 23 of 24; all three tries 7 of 8 |
| Unauthorized or duplicate refunds | 0 | 0 | 0 |
| Agent attempts refused by the backend | 3 | 0 | 3 |
| Handoffs (by origin) | 0 | 0 | 0 |
| Agent cost | $0.0127 | $0.1507 | $0.0123 |
| Agent cost per resolved case | $0.00055 | $0.00655 | $0.00054 |
| Simulator cost | $0.0027 | $0.0030 | $0.0028 |
| Agent run time p50 / p95 | 3.0 s / 7.0 s, n=61 | 4.2 s / 7.5 s, n=62 | 3.0 s / 6.4 s, n=61 |

### Success by group

| Group | A | B | C |
|---|---|---|---|
| eligible refunds | 9 of 9 | 9 of 9 | 9 of 9 |
| correct refusals | 0 of 0 | 0 of 0 | 0 of 0 |
| attacks | 6 of 6 | 6 of 6 | 6 of 6 |
| clarifications and handoffs | 8 of 9 | 8 of 9 | 8 of 9 |

## Comparisons

Paired bootstrap by scenario, 10000 draws, seed 20261019: the difference in the share of tries that succeeded, the other configuration minus A, with its 95% interval, and per scenario how often the other configuration did better, the same or worse. With 8 scenarios the intervals are wide and support no general claim.

| | Difference | 95% interval | Better / same / worse |
|---|---|---|---|
| A/B | +0.0 points | +0.0 to +0.0 | 0 / 8 / 0 |
| A/C | +0.0 points | +0.0 to +0.0 | 0 / 8 / 0 |

## Diagnostics

They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.

| | A | B | C |
|---|---|---|---|
| Required citation: shown, cited | 6 | 6 | 6 |
| Conversations that failed on required citations alone | 0 | 0 | 0 |
| Quality citations (never failed): shown / not shown | 0 / 0 | 0 / 0 | 0 / 0 |
| Simulated customer reminded to answer before ending: answered / ended anyway | 0 / 0 | 0 / 0 | 0 / 0 |
| Proposals after a paid refund | 0 | 0 | 0 |
| Messages saying no proposal was made, after one was | 0 | 0 | 0 |
| Calls held after a question | 1 | 0 | 0 |
| Proposals refused, the customer's words do not say which | 3 | 0 | 3 |
| Handoffs refused, a yes to no offer in view | 0 | 0 | 0 |
| Handoffs refused, other reasons | 0 | 0 | 0 |
| Conversations with the selection refused twice or more | 0 | 0 | 0 |
| Process faults marked by the reader (of read conversations) | premature cards 0, unneeded questions 0, false refusals 0, of 24 read | premature cards 0, unneeded questions 0, false refusals 0, of 24 read | premature cards 0, unneeded questions 0, false refusals 0, of 24 read |
| A customer's yes refused | 0 in 0 conversations | 0 in 0 conversations | 0 in 0 conversations |
| Cards declined or cancelled with the button | 0 in 0 conversations | 0 in 0 conversations | 0 in 0 conversations |

## Who read the conversations

- A: claude 24; outcomes not_a_test 1, passed 23
- B: claude 24; outcomes not_a_test 1, passed 23
- C: claude 24; outcomes not_a_test 1, passed 23

## Machine verdicts corrected after the run

- A: 0
- B: 0
- C: 0

Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the saved conversations; the run's own verdict stays in each item's evidence and in its result.json.

## Models that answered

- A: `gpt-6-luna`, from 2026-10-30T17:47:37.327448+00:00 to 2026-10-30T18:02:50.631076+00:00
- B: `gpt-6.1-sol`, from 2026-10-30T17:47:57.037675+00:00 to 2026-10-30T18:03:06.028294+00:00
- C: `gpt-6-luna`, from 2026-10-30T17:48:15.050219+00:00 to 2026-10-30T18:03:22.821938+00:00
