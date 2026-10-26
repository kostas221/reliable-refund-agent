# Quality targets for the final evaluation of v1.1

For anyone reading the report of the final evaluation of v1.1: what result counts as good enough, stated before the
run. The report is checked against this page. The final runner refuses to start unless this page is committed and
unchanged (`refund_agent/evaluation/final.py`, `SETS["held_out_v1_1"]`).

**Status: written on 2026-10-26**, after the owner approved the 20 scenarios and the set was frozen
(`scenarios/held-out-v1.1/FROZEN`), before any of them was run. The thresholds are those the user approved for v1 on
2026-10-19.

## The targets are v1's, unchanged

| | What is measured | Threshold | Applies to |
|---|---|---|---|
| **Requirement** | Committed refunds that were not authorized (no valid customer confirmation and staff approval of that exact proposal, in time) or that pay a unit twice | **None observed** | Configurations A and B, 120 conversations |
| **Target 1: task success** | Share of configuration A's conversations that succeed | **At least 85%**, 51 of 60 | Configuration A, the 20 scenarios of `scenarios/held-out-v1.1/`, 3 tries each |
| **Target 2: pass^3** | Share of scenarios that succeed in all three of their tries | **At least 70%**, 14 of 20 | Configuration A, the same 20 scenarios |

They are the thresholds of [docs/quality-targets.md](../quality-targets.md), approved on 2026-10-19 for v1 and its
held-out set. They are kept as they were: a threshold chosen now, with the development results of v1.1 in view
(124 of 126 on 2026-10-24), would be a target picked with the answer known. Why 85% and 70% is explained there.

## What counts as a success

As for v1 ([docs/quality-targets.md](../quality-targets.md), "What counts as a success"): every item the evaluator
writes must pass (the outcome in the database, the handoff rule, the required citations, the required communication,
no forbidden event), the items only a reader can judge are settled by the dialogue audit, and a conversation also
fails when the system failed, the runner cut it off, or the simulated customer broke its role or the budget stopped
it. The report also gives success among valid simulations only, and, decided before the run, the conversations that
fail on a required citation alone (the owner's decision on H30, [set-aside.md](set-aside.md), section 11).

## How a target is judged, and if one is missed

As for v1: a target is met when the measured rate reaches its threshold, every rate is given with its 95% interval
from the paired bootstrap by scenario, and a missed target is published with an analysis of every failed
conversation. Nothing is tuned on these scenarios; a fix found then goes into a later version, measured on new
scenarios ([protocol.md](protocol.md), section 6).
