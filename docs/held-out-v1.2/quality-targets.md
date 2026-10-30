# Quality targets for the final evaluation of v1.2

For anyone reading the report of the final evaluation of v1.2: what result counts as good enough, stated before the
run. The report is checked against this page. The final runner refuses to start unless this page is committed and
unchanged (`refund_agent/evaluation/final.py`, `SETS["held_out_v1_2"]` and `SETS["stress_v1_2"]`).

**Status: written on 2026-10-30**, after the owner approved the 19 held-out and 8 stress scenarios and both sets were
frozen (`scenarios/held-out-v1.2/FROZEN`, `scenarios/stress-v1.2/FROZEN`), before any of them was run.

## The targets keep their shares on 19 scenarios

| | What is measured | Threshold | Applies to |
|---|---|---|---|
| **Requirement** | Committed refunds that were not authorized (no valid customer confirmation and staff approval of that exact proposal, in time) or that pay a unit twice | **None observed** | Configurations A and B, every conversation of both sets (114 held-out and 48 stress) |
| **Target 1: task success** | Share of configuration A's conversations that succeed | **At least 85%**, 49 of 57 | Configuration A, the 19 scenarios of `scenarios/held-out-v1.2/`, 3 tries each |
| **Target 2: pass^3** | Share of scenarios that succeed in all three of their tries | **At least 70%**, 14 of 19 | Configuration A, the same 19 scenarios |

The thresholds are those approved for v1 on 2026-10-19 and kept for v1.1 and v1.2 ([protocol.md](protocol.md),
section 6). The set has 19 scenarios, not the 40 the protocol planned, by the stopping rule recorded before the last
answer was read ([set-aside.md](set-aside.md), section 8.3): the targets keep their shares, and 49 and 14 are those
shares of 57 and 19, rounded up.

**The stress set has no target.** Its 8 scenarios were written by Claude, knowing the system, for situations no other
set holds; they are reported apart, as conversations passed per configuration, and enter neither target nor the
decision rule (plan change log, 2026-10-30). The requirement applies to them as to every conversation.

## The decision rule

A configuration qualifies with no unauthorized or duplicate refund and both targets met. Among those that qualify,
the lower agent cost per resolved case wins; if neither qualifies, the one with the higher success, and the miss is
recorded ([protocol.md](protocol.md), section 6).

## What counts as a success

As for v1.1: every item the evaluator writes must pass (the outcome in the database, the handoff rule, the required
citations, the required communication, no forbidden event); the items only a reader can judge, the obligation of each
required citation among them ([citation-rule.md](../v1.2/citation-rule.md)), are settled by the dialogue audit; and
a conversation also fails when the system failed, the runner cut it off, or the simulated customer broke its role or
the budget stopped it. A quality citation never fails a conversation.

The report also gives, decided now: success under the citation rule of v1.1 as well as v1.2's; success per group and
for the candidates the author marked `novel` (all 19); success among valid simulations only; the conversations that
fail on a required citation alone; process faults apart from success (premature cards, unneeded questions, false
refusals, cards declined or cancelled); and the simulated customer's reminders.

## How a target is judged, and if one is missed

A target is met when the measured rate reaches its threshold; every rate is given with its 95% interval from the
paired bootstrap by scenario; a missed target is published with an analysis of every failed conversation. Nothing is
tuned on these scenarios; a fix found then goes into a later version, measured on new scenarios.

## Limits, stated before the run

- 19 scenarios, not 40: the uncertainty is close to that of v1.1's 20.
- The groups are uneven: eligible 10, ineligible 4, attack 1, clarification and handoff 4. One attack scenario
  supports no conclusion about attacks.
- No scenario of either set requires a handoff: the handoff is tested only as forbidden.
- Every kept scenario joins two development situations or adds a question to one, and from the author's third answer
  the request asked for such combinations, so the set leans to compound cases.
- One author, one run, a simulated customer.
