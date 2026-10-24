# Reliable Refund Agent

A customer-support agent that proposes refunds, obtains customer confirmation and staff approval, and executes
each authorized operation at most once. Evaluated through database state, event history, simulated customers and
controlled failure tests. Portfolio project #3 (Junior Applied AI / GenAI Engineer), after a RAG project and
Agent Action Guard.

The plan is **frozen**: `docs/plan.md` (version 4, in Greek, 2026-10-09). Read it before any design or code work.
It changes only because of running code, a failed test, a measured cost or real feedback, and every change is
logged with its date at the end of `docs/plan.md`. No new planning rounds.

## How to work with this user

- Answer in plain Greek, no jargon without a short explanation. Give a recommendation, not a menu.
- Code, docs, README, commit messages: English.
- Commits and pull requests WITHOUT any Claude attribution (no "Co-Authored-By: Claude", no "Generated with
  Claude Code"). Commit or push only when the user asks.
- The user runs every command that costs money (any call to a model API with the real key) in Git Bash (MINGW64)
  on Windows. Give the exact command, one per ```bash block, never PowerShell syntax. Claude writes code and runs
  free checks only.
- `.env` holds API keys: never print, read or echo it; only check that a key is present.
- Narrate each design decision while building (what and why), so the user can object. Tie every step to what it
  proves; the user gets discouraged by long work without a visible result.
- Before any paid run: zero-cost checks first (mock model end to end, read one logged prompt in full),
  predictions and the question written down before the run, a budget cap in the runner.
- Every result states its denominators, uncertainty and limits. Negative results are reported, not hidden.
- Windows console is cp1253: console output in ASCII (emoji crash it).
- Two roles (the user's request, 2026-10-19). Documentation (README, `docs/`, module docstrings that explain a
  design) is written as a professional technical writer would: for a named reader, the point first, one term per
  concept, structure by what the reader needs to do or check, examples, and dated history kept in change logs and
  results rather than in reference text. Ideas, design, implementation and code are done as a senior AI engineer
  would: evidence over assumption, measured trade-offs, the simplest design that holds, tests that fail without the
  fix.

## Rules from the plan (short; details in docs/plan.md)

- v1 scope (§2): one refund flow, English only, staff approval for every refund, one fictional shop and currency,
  local PostgreSQL with a test ledger, customer chat + staff console, Docker + mock mode + video. A new feature
  needs another one moved out of v1 (scope rule, §15).
- The backend is the authority (§5-6): LangGraph keeps the conversation, tool results, pending IDs and routing,
  and grants nothing. Nodes call domain services; services check actor/session, ownership, policy, amount, state
  transition, approval bound to the exact immutable proposal, and execute in one transaction. Idempotency key AND
  the shared refundable balance checked in the same transaction. At most one committed operation per approval;
  retry returns the same receipt.
- The 15 failure cases (§13) and the "authorization and tool-integrity checks" table (§10.4, about 15 cases,
  checked in the database, configurations A and C) are deliverables, written with the backend, not at the end.
- Models (§9): agent GPT-6 Luna (`low`, `none` tried in the pilot; chosen by cost per correctly resolved case),
  reference GPT-6.1 Sol (configuration B), simulator Luna with a dialogue audit. All through the Responses API
  behind a ModelAdapter. No live model call before the pilot is approved.
- Evaluation (§10-11): 10 development + 20 held-out scenarios; held-out frozen and never used for tuning;
  pass^3 = share of scenarios that succeed in all three tries; paired bootstrap per task for A/B and A/C;
  quality targets written after the pilot and before the final test.

## Now

Phase 6 (§15) done: the final evaluation ran on 2026-10-19 (`runs/final-20261019T201207Z`, $0.585) and is read and
reported (`docs/final/results.md`, plan change log 2026-10-20). A missed both targets and met the requirement:
success 41/60 (target 51), pass^3 11/20 (target 14), no unauthorized or duplicate refund in 180. B (Sol) 50/60, +15
points at 16.6 times the cost per resolved case; C 40/60, the agent never tried to pay without approval. Causes of
A's 19: citations of sections the policy word search never showed the agent (8), handoffs the policy's exceptions
clause can be read to require (5), handoffs with no request (2), a true but not deciding reason (2), no clarifying
question (2), a simulator fault (1). The evaluator's amount check was fixed after the run (whole amounts without
cents) and applied to the saved results; the user's audit share was 69 conversations, read with help from another
AI model. v1 is labelled as having missed both targets; the held-out set is spent (closing commit b5ae4b1).

The v1.1 cycle (plan change log, 2026-10-20; spec from `docs/improvement-review-2026-10-20.md`, its final consistency
check approved by the user as the policy v2 specification). Each step is measured on its own against v1, paired by
scenario (`python -m refund_agent.evaluation.report compare`). Step 0 done: runs load the policy version their scenarios
declare (`policy_for`, checked in `seed`); H01-H20 copied to development as D11-D30 (`derived_from`, held-out files
unchanged); diagnostics in the report (citations shown or not, handoffs by origin, proposals after a receipt),
reproducing the v1 counts. Step 1 done (`runs/pilot-20261020T110559Z-gpt-6-luna-none`, results in
`docs/pilot/results.md`): the whole policy v1 in view gained 2 conversations and lost 6 to handoffs its text can be read
to require; the user's reading of 10 conversations is pending, and Claude's verdicts are shown only after it. The order
changed: policy v2 before the assessment tool. Step 3 done (`runs/pilot-20261020T170431Z-gpt-6-luna-none`, results in
`docs/pilot/results.md`): 77/90 (step 1 64, v1 70), D11-D30 53/60 (v1 41), 0 unsafe; paired +14.4 points against step 1
(95% +0.0 to +28.9). Forbidden handoffs 14 to 4, but 3 were labelled `customer_asked` with no request from the customer
(the one code the backend cannot check); clarification (D09, D17) 0/6; 2 D10 simulations ended with a provider 403. The
user reads 9 conversations (`user-review/`), and step 1's 10 are still pending; Claude's verdicts are shown only after.
Step 2 done (`runs/pilot-20261021T211812Z-gpt-6-luna-none`, results in `docs/pilot/results.md`): 79/90, D11-D30 54/60, 0
unsafe; +2.2 points against step 3 (95% -5.6 to +10.0). No `customer_asked` handoff without a request (6 false attempts
refused); clarification 1/6 (the assessment did not bring it); two defects in text the agent reads: the assessment's
'refused' next step overrode a named handoff (D22, 17/18 required handoffs), and the unasked test-ledger line rose from
20 to 35 and made customers doubt the refund (D01, D11). Step 2 repairs done
(`runs/pilot-20261021T224855Z-gpt-6-luna-none`, results in `docs/pilot/results.md`): 81/90, pass^3 24/30, 0 unsafe; +2.2
points against step 2 (95% -5.6 to +11.1), +12.2 against v1 (+1.1 to +25.6). 18/18 required handoffs; the unasked
test-ledger line 0/90 (step 2: 35); one proposal denial left (D17); required citations 24/27 (D20 missed remaining
twice). Contrasting development cases written (plan change log, 2026-10-22): D31-D42, six pairs that differ in the
behaviour that should change (ask which item or propose at once; hand off or not; a question after a receipt), with a
new criterion `proposes_without_asking` for the explicit side, mock runs and predictions ("Contrasting cases,
baseline"). Their baseline (`runs/pilot-20261022T000917Z-gpt-6-luna-none`, results in `docs/pilot/results.md`): 31/36,
0 unsafe; asking which item 4/6 (D33 3/3, D31 1/3), no unnecessary question 6/6; three new weaknesses: every clarifying
question reached the customer twice in one message (the adapter joins all message items and ignores their
commentary/final_answer label), a `customer_asked` handoff quoting "Can I cancel it?" accepted by the backend (D38), a
shipping question handed off as a shipping refund (D39, 2/3; the user reads its opening as a question, so the scenario
stands). The user asked for careful fixes of causes rather than trial runs (2026-10-22): code defects first, each with
a test that fails without it, then the language judgments one at a time. Bug fixes written (plan change log,
2026-10-22; second review `docs/remaining-gaps-after-repairs-2026-10-22.md`): the adapter shows the `final_answer`
text and sends the model back every text item it gave, with labels and in order; `customer_asked` needs the quote in
the customer's latest message, and that message must name a person with no negation before it or say yes, with no
negation, to the agent's offer of one in the message just before (12 contrasting cases in
`tests/test_request_for_person.py`, after a third review found the first rule too loose; replayed on the last three
runs: keeps the 30 genuine, refuses only D38's); the refusal's named case reads every reason, never for an order in
transit, and names only the units a dispute can carry; a repeated proposal call tells its status and next step from one
read, and a rejection's reason. Their run (`runs/pilot-20261022T165428Z-gpt-6-luna-none`, results in
`docs/pilot/results.md`): 112/126, the same as each scenario's last run (paired +0.0, 95% -5.6 to +5.6), 0 unsafe,
27/27 required handoffs, 11/11 predictions right; no handoff on words that ask for no person, but one false refusal of
a genuine yes to an offer the rule did not recognize (D37 try 3); no doubled message, though the case was not
exercised; clarification 3/12: D09, D17, D31 never ask, and in D33 the question went out as commentary with a tool
call and the agent proposed without waiting. Review after the 126 conversations (2026-10-23,
`docs/review-after-126-conversations-2026-10-23.md`): reproduced, direction adopted, its new components (an
`ask_customer` tool, a selection ID, a recorded offer state, an intent model) deferred with a trigger (plan change log,
2026-10-23). Three code changes written, not yet measured: a selection check in `refunds.propose` (`units_named`,
`refund_agent/selection.py`: among look-alikes, a proposal needs the customer's words that tell them apart, or their
answer to a question that named them); a question brake in the graph (an answer that asks the customer ends the turn,
its calls answered as not run); the person-request rule repaired (scoped negation and withdrawal, "cannot", wish-form
offers, the speaker's own role, a separate refusal for a yes with no offer in view). Replayed on the saved logs
(`python -m refund_agent.evaluation.replay`): 32 of 602 proposals refused, all first proposals of failed D09, D17,
D31, D33 tries; 3 of 3,946 answers held; 2 of 68 handoff decisions changed (D38 try 1, D37 try 3). Their run
(`runs/pilot-20261023T144102Z-gpt-6-luna-none`, commit a8b5869, results in `docs/pilot/results.md`): 125 of 126 (the
computer slept during D42 try 2, the runner stopped on a database drop, D42 try 3 is missing and counts as failed),
118 of 126, pass^3 37 of 42, 0 unsafe, 27/27 required handoffs, 13/13 predictions right; paired +4.8 against the last
run (95% -2.4 to +12.7), +17.8 against v1 on 30 (+6.7 to +31.1). Clarification 12 of 12 (was 3 of 12): 9 proposals
refused by `units_named`, each followed by the question; D32 and D34 6 of 6 at once; the brake was never exercised.
Failures: D39 x3 (shipping question), D20 x2 (citation), D15 try 2 (scenario ambiguity), D13 try 1 (a false
"deadline passed", a date error). Review after the selection check (`docs/review-after-selection-check-2026-10-23.md`):
its 5 selection counterexamples reproduced and fixed (the check reads messages in order, clause by clause: excluded
words, the latest word per item, "only", counts with the item's name, a yes to a question that named that item
alone; the same 41 refusals in 697 recorded proposals); `shipping_refund` needs the customer's latest words naming the
shipping charge (all 16 recorded attempts had none); the `remaining` citation beside a paid request's receipt; D15's
role revised (the customer defers an offered person; D15 reported apart across that date); the runner holds the
simulator model fixed (`--simulator-model`), survives a failed database drop and keeps Windows awake. 18 planted bugs
caught. The comparison of Luna none and Sol low on this version (`runs/pilot-20261023T185612Z-gpt-6-luna-none`,
`runs/pilot-20261023T201842Z-gpt-6.1-sol-low`, commit cb359eb, same simulator; results in `docs/pilot/results.md`):
the decision rule chose **Luna none**. Both qualify (0 unsafe; Luna 120/126, Sol 123/126; pass^3 39/42 each); Luna
costs 12.6 times less per resolved case ($0.00044 against $0.00551); Sol minus Luna +2.4 points (95% -3.2 to +8.7),
$0.21 per extra resolved conversation. Sol wins D39 (answers the shipping question; Luna hands it off, quoting the
question, and the backend accepts it: the rule checks only that the words name shipping) and D20 (`remaining`
cited); Sol loses D13 and D28 (a person offered for a side question, accepted; the scenarios forbid a handoff, the
D15 question again). 12 of 15 predictions right, 1 partly, 2 wrong (D20; response time, which varied with the
provider's hour). Luna none stays the configuration, Sol low the reference B; Sol's 0 refused attempts against
Luna's 20 are recorded beside the rule. Final fixes after the review of the model comparison (2026-10-24, plan
change log; `docs/review-model-comparison-2026-10-24.md`), each with failing-first tests: `shipping_refund` rests on
the customer's yes to the agent's offer of a staff member for the shipping charge (instructions v8); a fact line
from the records after an answer that states a refund paid before or an order not delivered without its section
(`agent/facts.py`, counted apart in the diagnostics); the customer's cancel button stores a notice to the agent
(migration 0007) and a handoff's result says what it closed; D13, D28, D39, D40 roles say how the customer answers an
offered staff member (reported apart across the date). Replayed: the 9 shipping handoffs of the comparison refused at
first, the fact line on exactly the 4 missed citations and 5 true places. 1352 tests and 4 browser tests pass, 18
planted bugs caught. The confirmation run (`runs/pilot-20261024T120131Z-gpt-6-luna-none`, commit 41f7fab, $0.075,
results in `docs/pilot/results.md`): 124/126, pass^3 41/42, 0 unsafe, 27/27 required handoffs, 57/57 required
citations (1 by the fact line), 9 of 10 predictions right; paired +3.2 against the run of 2026-10-23 (95% -3.2 to
+10.3), +2.6 on the 38 unrevised scenarios (+0.0 to +7.0, no loss), +20.0 against v1 on 30 (+6.7 to +34.4). D39 0 to
3, D40 3/3 on a yes, the question brake exercised live for the first time. Regression in D28 (1/3) from the
cancellation notice: it starts an agent run with no customer message, and Luna answered it with a new proposal
(unasked in try 2); the runner cancelled each, to the round limit (nothing paid). Fixed with the user's approval
(plan change log, 2026-10-24): the cancellation notice is stored and delivered but starts no run
(`Agent.notify(..., wake=False)`); the agent reads it at the customer's next message; staff decisions still wake it.
Failing-first tests, 1350 tests and 8 browser and API-surface tests pass, 21 planted bugs caught. Next: the user runs
D28 alone, 5 tries (predictions written: `docs/pilot/predictions.md`, "D28 after the silent cancellation notice");
then the freeze and 20 new held-out scenarios by an independent author, in their own locked set, run with A (Luna
none), B (Sol low) and C, so that which model is better on unseen scenarios can be stated (the user's request; the
wording is written in the final predictions before the run). 126/126 on development would show only that the cases
the rules were built on are solved. The user reads 5 conversations of the confirmation run (`user-review/`),
7 of the comparison
(`runs/pilot-20261023T201842Z-gpt-6.1-sol-low/user-review/`, four questions), 6 of the selection check run, and 10
of step 1 and 9 of each of steps 3, 2 and the repairs (`user-review/`); Claude's verdicts are shown after.
Development runs: Claude reads all, the user reads what Claude fails or notes. Phase 7 (video, code licence, external
test, CI on a remote) after v1.1.

## Environment

- Windows 11, Git Bash. Python with uv (as in Agent Action Guard); ruff, line length 120.
- Data: an Olist subset (Kaggle, "brazilian-ecommerce"), downloaded by the user; raw data stays out of git
  (`data/raw/`), with provenance and checksum. Mock mode must work with fully synthetic fixtures.
- Related project: `C:\Users\zosim\agent-action-guard` (approval gate bound to the exact call and used once, run
  manifests, metrics with intervals). Reuse ideas and code from it, but never edit it from here; it is being
  finished (release 0.3) in another session and its benchmark runs use the same OpenAI account.
