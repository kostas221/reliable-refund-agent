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
Failing-first tests, 1350 tests and 8 browser and API-surface tests pass, 21 planted bugs caught. D28 alone
(`runs/pilot-20261024T164827Z-gpt-6-luna-none`, commit 1a46a3c, $0.0028): 5/5, 5 of 5 predictions right; the notice
added with no agent run, no new proposal. **The v1.1 implementation is frozen** (commit 1a46a3c, fingerprint
c3416bd9...). The final evaluation follows `docs/held-out-v1.1/protocol.md` (2026-10-25): the user gives
`docs/held-out-v1.1/author-package.md`, and nothing else, to a model in a fresh conversation with no memory of the
project, and saves its 28 candidates (10/6/6/6) unchanged as `docs/held-out-v1.1/author-output.md`; candidates that
repeat a development situation or do not follow the policy are set aside, and the first 20 in the author's order are
kept; Olist orders drawn by lot; Claude writes the files with a conversion log and adds nothing; checks; a new locked
set `scenarios/held-out-v1.1/` that the final runner selects and records; predictions with the wording of the
Luna-Sol comparison; one run of A, B and C, so that which model is better on unseen scenarios can be stated (the
user's request). Nothing in the agent changes once the scenarios exist. Authoring so far (`set-aside.md`): 18 of
the first 28 repeated development; the package was corrected once, with facts only (`author-correction.md`: the
clock moves a minute per event, a declined card ends cancelled, each citation is checked alone, no zero prices); the
author's second answer (`author-output-2.md`, 51 candidates) left 17 of 20 kept; the third (`author-output-3.md`,
H73-H86) filled eligible (H74); a second correction (`author-correction-2.md`: a proposal sent to staff is recorded
`ineligible`, and a staff case is handed off only after it) fixed H47 and H77 (`author-output-4.md`). 20 of 70 kept
(`set-aside.md`, section 10): eligible H26 H28 H29 H30 H50 H52 H55 H74; ineligible H35 H58 H60 H61; attack H40 H41
H42 H63; clarification_handoff H47 H72 H77 H80; the owner approved them and the decisions of section 11 (H61 for the
repeat H59, H30 as written, the second model's answer `author-b-output.md` a record only). Converted on 2026-10-25:
`scenarios/held-out-v1.1/` (split `held_out_v1_1`), written by `scripts/convert_held_out_v1_1.py` from the author's
text, Olist orders by lot (`data/olist/subset-v1.1.json`), `conversion-log.md`, `decision-notes.md`; free checks pass
(`tests/test_held_out_v1_1.py`, `tests/acceptance/test_held_out_v1_1_mock.py`: correct scripted runs pass 20/20, wrong
ones fail). The final runner takes `--set held_out_v1_1`, refuses v1's spent set, checks and records the set's
FROZEN. Only evaluation files changed since 1a46a3c. The owner approved the 20 files; **the set is frozen**
(2026-10-26, `scenarios/held-out-v1.1/FROZEN`); targets are v1's (`docs/held-out-v1.1/quality-targets.md`) and the
predictions are written (`docs/held-out-v1.1/predictions.md`: A 40 to 52 of 60, citations the main cause, B 0 to +15
points with an interval including zero, under $1); the report counts conversations failed on citations alone. The
final run (`runs/final-v1.1-20261026T125831Z`, $0.57), before the audit: A 39/60, pass^3 10/20; B 45/60 (15/20); C
39/60; 0 unauthorized or duplicate in 180; B-A +10 points (95% -10 to +30). A's 21 failures: 17 a missing citation
the author required, 1 the `proposes_without_asking` pre-check (a "shall I start?" after a question; B 6), 1
simulator fault (H41 try 3, A and C: ended on an offer it should accept), 2 behaviour (H77: handoff tried before a
proposal, refused, then by the customer). Decided (plan change log, 2026-10-26): v1.1 closes as measured, targets
missed, after the audit and report; then a v1.2 cycle of fixes by category, not scenario: fixes first, measured on
new development scenarios, and the system frozen; then more than 20 new held-out scenarios (proposed 40) from an
independent author, grading rules written before any run, the result also given under v1.1's rules, and nothing in
the system changed after (plan change log, 2026-10-26, the corrected order). v1.2 fixes 1-6 written (plan change
log, 2026-10-26 and 2026-10-27; nothing committed, no paid run): the `proposes_without_asking` pre-check fails only
with no proposal and flags, quoted, a question that may ask which items for the reader (words never fail it); a
`shop_decided` handoff that names order and units is decided and recorded by the backend (`refunds.refer_to_staff`);
a declined card is told to the agent (migration 0008); a handoff's result gives its sections and the fact line says
the ones the announcement leaves out; an eligible proposal's result gives window, validity or approval when the
records call for them, naming the items each earlier request covered (`refunds.proposal_context`; fixture
`invalidated` now seeded as an order or policy change); simulator instructions v2, a reminder once when it ends in
front of the agent's last answer's question (fact lines skipped), reminders counted and an end after one flagged.
A run comparison names every change of measurement (evaluator, runner, simulator, seeding, scenario files). The
outside review of 2026-10-27 (`docs/review-v1.2-follow-up-2026-10-26.md`) was checked finding by finding before
adoption. v1.1 with Claude's audit and the dated corrections: A 40/60 (11/20), B 51/60 (17/20), C 38/60; B-A +18.3
(95% +6.7 to +33.3); as run +10.0 (-10 to +30). The pre-registered decision rule chooses **Sol** for v1.1 in both
views (final after the owner's reading); Claude's earlier "keep Luna" skipped the qualifying step and is withdrawn.
The owner's reading under the recorded rule is 81 conversations, not 30. Sequence (plan change log, 2026-10-27): A
free checks and instructions v9 (done: `prompts/agent-v9.md`, four targeted changes, contract tests in
`tests/test_model_adapter.py`); B the citation rule, rescoring of saved dialogues under both rules, author package
v2 (done 2026-10-27, the owner's "συνεχισε" read as approval: `docs/v1.2/citation-rule.md`, 39 of 40 required
citations kept with obligations, H30's a quality citation, D35 kept required after the scenario check refused it;
v1.1's A 42/60 under it; the evaluator leaves a shown citation with an obligation to the reader, and the report gives
the v1.1-rule result too; `docs/held-out-v1.2/author-package.md`, 60 candidates H101-H160, and `protocol.md`); C
done (v1.1's 20 copied to development as D43-D62 with obligations, D46 quality; the confirmation run
`runs/pilot-20261027T144002Z-gpt-6-luna-none`, commit 795d430, $0.108, results in `docs/pilot/results.md`): 186/186,
62/62 in all three tries, 0 unsafe, Claude read all 186 and failed none, 117/117 obligations told; paired D01-D42 +1.6
(95% +0.0 to +4.8), D43-D62 +33.3 against v1.1's A (+16.7 to +51.7), 0 worse, combined product and measurement
change; 12 of 13 predictions right (3 wrong, above the range). Weaknesses recorded, not repaired: a fact line stored as
an agent message hides an offer from the yes check (D40 try 2, since 2026-10-24, fails safe; repair: skip fact lines),
offers the person rule cannot read, the customer's own shipping request refused until a yes, v9's words-first partly
followed (15 of 21 proposals before the customer wanted the allowed amount; nothing wrong paid). Stopping rule: no
safety defect, no regression this bundle caused, so **the system is frozen** at 795d430, fingerprint 96e452ab...
(`docs/held-out-v1.2/protocol.md`); step C committed as 353ebff. The outside review of 2026-10-28
(`docs/research-generalization-2026-10-28.md`) was verified on 795d430 with free probes; the 2026-10-23 trigger for
the recorded offer had fired on 2026-10-24 and 2026-10-27 unrecorded. The owner reopened the freeze before the
author got the package (plan change log, 2026-10-28) for two code fixes and process measures, no change to the
agent's tools, instructions, policy or the author package: the fact line uses each order's latest read and speaks only
of an order the answer names (`agent/facts.py`); fact lines are stored marked (migration 0009) and the two checks that
pair an answer with the agent's message before it skip them (`refunds._written`, `_look_alikes_unnamed`); the report
counts process faults apart from success (reader-marked `process = [...]` in the audit: premature_card,
unneeded_question, false_refusal; automatic: a customer's yes refused, cards declined or cancelled). Failing-first
tests; replay on step C: 1 of 51 handoff decisions changes (D40 try 2), the fact line is the same on 3,128 + 337 saved
answers; 18 planted bugs (scratchpad `planted_bugs_pre_d.py`); committed as d404242. The recorded offer and selection
by candidate IDs wait for after step D. Their confirmation run (`runs/pilot-20261029T113311Z-gpt-6-luna-none`,
$0.103, results in `docs/pilot/results.md`): 185/186, 61/62 in all three tries, 0 unsafe; against step C -0.5 points
(95% -1.6 to +0.0), 0/61/1, measured the same way. The one failure, D49 try 2: the customer asked in words for a person
about shipping, the shipping handoff was refused (yes-to-offer rule) and the customer_asked one accepted, while the
scenario requires the agent's; not caused by the fixes (no fact line, check unchanged); D49's expectation is for the
scenario review after D, unchanged now. D40 try 3: a yes after a fact line accepted at once; 0 yes refused (step C 3);
3 fact lines, all true and bound. First process baseline: premature cards 14 (15 of 21 as step C counted), unneeded
questions 1 (D34 try 1), false refusals 5 (all the shipping rule); a doubled final answer once (D09 try 2, 1 of 2,572).
8 of 9 predictions right, 1 partly. Stopping rule held: **the system is frozen again** at d404242, fingerprint
721e9891... (`docs/held-out-v1.2/protocol.md`). Reopened by the owner on 2026-10-29, before the author got the package,
for a last bundle pre-registered in the plan change log, after an outside critique checked with free probes: the
shipping handoff also on the customer's own request for a person for the shipping charge (the record says which basis);
an eligible assessment's next step says the allowed amount in words first when the customer asked for more (an
experiment, reverted with one more confirmation run if premature cards do not fall to 7 or fewer of 186, or unneeded
questions pass 2); identical consecutive answer items shown once; in measurement, the package's handoff origins (both
where the customer asked for or accepted a person in a case the policy names) and both origins for D40 and D49. Its run
(`runs/pilot-20261029T143336Z-gpt-6-luna-none`, commit 4676e85, $0.106, results in `docs/pilot/results.md`): 184/186,
60/62, 0 unsafe; D15 try 3 failed (the role's "wait for it" read as a yes to an offered staff member, and the agent
handed off before the refund asked for in the same message: the order of work is recorded for after the held-out set),
D35 try 3 a fault of the simulated customer; (a) worked (D49's own requests for a person accepted at once, false
refusals 5 to 3), (c) not exercised, (b) missed its bar (premature cards 11, bar 7) and was reverted by its rule; the
roles of D15 and D35 now say no to an offered staff member, with a stronger guard test; 7 of 9 predictions right, 1
partly, 1 wrong. The last confirmation run without (b) (`runs/pilot-20261030T111724Z-gpt-6-luna-none`, commit 829f6ec,
$0.105, results in `docs/pilot/results.md`): 186/186, 62/62 in all three tries, 0 unsafe, 9 of 9 predictions right; the
revised roles declined the offer 6 of 6; premature cards 12, false refusals 3 (D40, by design). **The system is frozen**
at 829f6ec, fingerprint 5ff1fcad... (`docs/held-out-v1.2/protocol.md`); the user reads 4 of its conversations
(`user-review/`). Step D, authoring (2026-10-30, `docs/held-out-v1.2/set-aside.md`, plan change log): four answers
of the author (`author-output.md` to `author-output-4.md`) gave 4/60, 2/73, 11/68 and 2/69 candidates that repeat no
development scenario, under the strict reading the owner approved (borderline ones set aside, not used as extras). From
the third answer the request asked each candidate to combine two variations of the package (a protocol deviation,
recorded after sending); a stopping rule ended the requests. **The held-out set is 19, not 40** (eligible 10,
ineligible 4, attack 1, clarification_handoff 4); targets keep their shares (49/57 conversations, 14/19 pass^3). The
owner approved the set and added a **stress set**: 8 scenarios Claude wrote for four situations no other set holds
(`docs/held-out-v1.2/stress-scenarios.md`), run beside the 19 and reported apart with no target; a fifth situation (two
refunds in one conversation) cannot be built with the frozen harness. Converted on 2026-10-30
(`scripts/convert_held_out_v1_2.py`; `scenarios/held-out-v1.2/`, `scenarios/stress-v1.2/`; Olist draws
`subset-v1.2.json`, `subset-stress-v1.2.json`; conversion logs; `decision-notes.md`): only evaluation files changed
since 829f6ec (schema splits, runner sets with v1.1 now spent, manifest, report lookups). Free checks pass: fidelity
tests, 27 correct scripted conversations pass and wrong ones fail, 9 of 9 planted file errors and 5 of 5 runner errors
caught. No scenario of either set requires a handoff (a coverage limit, recorded). The owner approved the 27 files;
**both sets are frozen** (2026-10-30, `FROZEN` in each folder); targets keep their shares
(`docs/held-out-v1.2/quality-targets.md`: 49/57, 14/19, no unsafe refund in A or B; no target for the stress set) and
the predictions are written (`predictions.md`: A 42 to 53 of 57, target 2 likely missed, citations the main cause, B 0
to +12 with an interval including zero, under $1.50). Both runs done at fce42f1 (`runs/final-v1.2-20261030T170445Z`, $0.42; `runs/stress-v1.2-20261030T174734Z`,
$0.18); Claude read all 243 and changed no machine verdict: A 50/57, pass^3 16/19 (both targets met), B 54/57
(18/19), C 49/57 (15/19), 0 unsafe; stress 23/24 each, 3 S04 conversations not a test. The report now reads the
run's set (`refund_agent/evaluation/sets.py`: no target for the stress set). Next: the owner reads the 73 the rule
selects, without Claude's verdicts; then `docs/held-out-v1.2/results.md`, the decision rule, commit on the owner's
word. v1.3 reasoning experiment (plan change log, 2026-10-31; `docs/pilot/results.md`): copies D63-D89 of both
sets, Luna none/low/medium, 81 conversations each, $0.159, 0 unsafe; 73/75/73; low and medium ask first where
two items fit (6 of 6 each, none 0 of 6 without the backend); D75 fails at every level; the pre-registered rule
kept none (3 more needed, low +2); the owner chose **low**, a recorded deviation (plan change log, 2026-10-31), so
v1.3's repairs are measured with Luna low against the low run; the final runner's A still records v1.2's none. Repair 1 (H255) written,
not measured (plan change log, 2026-10-31): `eligibility.window_deadline()` (used by `evaluate()` too) gives the
agent's order list `refund_deadline` and `refund_deadline_passed`; the late-and-not-returned advice no longer says
"must arrive first" alone; instructions v10; 8 of 8 planted bugs caught; the risk to watch is D10 (late, earlier
on-time proposal, a staff case). Repair 2 (H281) written (plan change log, 2026-10-31): `selection.py` groups
products of different names the customer's words fit equally, told apart by name words and nouns; replay on 1,819
saved proposals: 4 more refused, all wrong, no correct one; two defects found by the release brief's checks
(exclusion, changed choice) fixed, 11 of 11 planted bugs. The owner adopted `docs/release-brief-2026-10-31.md` as
the closing plan (plan change log, 2026-10-31), in this order: full suite, commit and the registered confirmation
run of all 89 scenarios with Luna low (`docs/pilot/predictions.md`); close v1.2 (the owner's reading of 73, results);
a local live-model mode in the app, whose entry point serves only `ScriptedModel` (mock stays default, a budget per
session, the owner starts each paid one); handoff checks and the five-person trial; README, Docker, CI, licence,
video. No MCP in this release. The confirmation run (`runs/pilot-20261031T183540Z-gpt-6-luna-low`, commit 0b79ad2,
$0.156, results in `docs/pilot/results.md`): 261/267, pass^3 85/89, 0 unsafe; D75 0 to 3 of 3, D10 3/3, the selection
check never had to act (low asked first 21/21); four citation losses (D79 x2, 15/15 before; D72; D41), not traced
to the repairs; 9 of 9 predictions right; the stopping rule allows freezing v1.3's agent at 0b79ad2 on the owner's
word. The owner chose instead to fix the four citation losses first (plan change log, 2026-10-31, a recorded
deviation): (A) a proposal that replaces the conversation's open one gives `approval` in its result
(`refunds.proposal_context`); (B) a fact line after an answer to the customer's question about shipping charges, where
the money goes, or a cancelled refund card or request, when the answer lacks `shipping`, `payment` or `approval`
(`agent/facts.py`: the customer's latest message asks, no event since). Failing-first tests, 14 of 14 planted bugs
(scratchpad `planted_citation_fixes.py`); replay on 5,812 saved answers: 8 lines, all after such a question (the
first draft gave 32, 22 wrong, and was narrowed); committed as 80c5a0b. Their run
(`runs/pilot-20261101T131628Z-gpt-6-luna-low`, $0.154, results in `docs/pilot/results.md`, "v1.3, the citation
fixes"): 264/267, pass^3 86/89, 0 unsafe, Claude read all 267; paired +1.1 (95% -0.7 to +3.4); fix A worked (D79 1 to
3 of 3, the agent cited the section it was given), fix B never fired (D41, D69, D72 cited by the agent itself, 9/9,
chance); lost D13 try 2 (a false "deadline passed" against `refund_deadline_passed: false`, as on 2026-10-23; repair
recorded for after the freeze) and D34 try 1 (an unneeded "which order?"), neither touched by the fixes; 8 of 9
predictions right (5 wrong: no line fired). **v1.3's agent is frozen at 80c5a0b** by the pre-registered rule;
committed. The product's model (plan change log, 2026-11-01, the owner's point): expected cost per conversation =
model cost + failure rate x $1 per failure (set by Claude at the owner's request, conservative against Gartner's
$13.50 median assisted contact); on v1.2's final run Luna $0.123, Sol $0.059 (break-even $0.08; written after seeing
those data, gain +7, 95% +0.0 to +19.3). v1.2's own rule stays as written and is reported beside it; the owner
chooses at v1.2's close; if Sol, one v1.3 confirmation run with Sol low first (~$2). No Haiku trial. An outside
critique of the closing plan (2026-11-01) was checked point by point and adopted (plan change log): the $1 criterion
is an assumption ("with $1 and the observed difference, Sol is preferred", the overclaim removed); the live mode's
completion criteria add a shared budget under concurrency (the `Budget` has no lock and lives in memory, notices are
delivered from a background thread), no silent reset on restart, and a clear recoverable state when the budget runs
out with an approval pending; false deadline claims are measured free before the human trial and a bounded repair
decided after the model choice, correcting the answer before the customer sees it; one trial participant plays staff.
**v1.2 is closed** (`docs/held-out-v1.2/results.md`): the owner waived the reading of the 73 (a recorded deviation);
Claude's second check confirmed 68 and added `explains_refusal_reason` to 5 H255 conversations already failed (no
outcome change); A 50/57, 16/19, both targets met, 0 unsafe in 162; B 54/57; no difference shown (+7.0, 95% +0.0 to
+19.3); the pre-registered rule chooses Luna, the $1 criterion Sol; predictions 5 right, 3 partly, 2 wrong; committed.
The author: GPT-6.1 Astra in ChatGPT (the owner), dated 2026-10-30 from the records (the owner recalled 2026-10-25,
v1.1's date). **The owner chose Sol low as the product's model** (plan change log, 2026-11-01); its v1.3 confirmation
run on all 89 (budget $4, predictions "v1.3, the product's model") checks the system with Sol and cannot rank models
(Luna low 264/267 on development). A Sonnet comparison needs new unseen scenarios and an Anthropic adapter: after the
release unless the owner decides otherwise. The run was cut off by the provider (no credit) at D51 try 2: D01-D50
count from `runs/pilot-20261101T154122Z-gpt-6.1-sol-low` (D51-D78 voided, `voided-no-credit/`), D51-D89 ran again
(`runs/pilot-20261101T163038Z-gpt-6.1-sol-low`), same fingerprint 4584800d, joined in
`runs/pilot-20261101T163038Z-gpt-6.1-sol-low-joined` for reading and the report (results in `docs/pilot/results.md`,
"v1.3, the product's model"): $1.58, 266/267 (D85 try 2 a simulator fault), pass^3 88/89, 0 unsafe, Claude read all
267; process faults 0/0/0 (Luna low 7/1/2), 0 false deadline claims in 52; paired against Luna low +0.7 (95% +0.0 to
+1.9), 2 better, 0 worse; 10 of 10 predictions right. Stopping rule held: **Sol low is the model of the live mode and
the trial**, agent unchanged at 80c5a0b. To watch: D81 tries 2-3, a new card at once after a button cancellation and a
typed yes (nothing paid). The live-model mode written (plan change log, 2026-11-01; not yet tried with the real
model): `python -m refund_agent.api --live --budget-usd X --prices-checked DATE` (mock stays the default, Sol low
unless named, the owner starts each paid session); one `Budget` for the whole server with a lock and per-attempt
holds (`agent/costs.py`), spend kept in `model_spend` (migration 0010) so `--keep` goes on from it, a stop by the
budget or the provider's credit is a pause (503 `agent_paused`, decisions stay pending uncounted, `GET /api/mode`
and a banner on every screen), resumed by `--keep` with a larger budget; `--keep` also retries decisions whose
delivery failed three times; `OutOfCredit` stops the runners at the provider's no-credit refusal; requests logged
to `runs/live-*/` (git-ignored); planted bugs in scratchpad `planted_live_mode.py`. Deadline claims: no repair
before the trial (Sol 0 of 52), each trial session checked. Sonnet comparison stays after the release (the owner
asked; reasons in the plan entry). `--resume` for the pilot runner still for later. 2669 tests (browser included)
and 54 screen tests pass, 26 of 26 planted bugs caught; committed as d26d584. The owner's first paid live session
(D01, Sol low, three parts on one database, $0.0168; results in `docs/pilot/results.md`, "Live mode: the first paid
session"): one refund paid once, a pause at $0.05 that sent nothing and kept the message, a restart that answered it
first; `model_spend` and the request logs agree; 6 of 6 predictions right; a `payout` citation that did not fit,
recorded. The Sol-Sonnet comparison set: author package `docs/held-out-v1.3/author-package.md` (60 candidates
H401-H460, Appendix A lists the 89 development situations; `tests/test_author_package_v1_3.py`); the author answered
72 (H401-H472, now `docs/held-out-v1.3/author-output.md` and `-2.md`; they had been saved over v1.2's files, which
are restored); a reviewer read all and selected 39 (`selected-39-*`, H463 removed by the owner; protocol section 2
records the early reading). **The owner moved the comparison before the trial** (plan change log, 2026-11-02): Sol
low against Claude Sonnet 5.5 (`claude-sonnet-5-5`) at effort low, the same simulated customer (Luna low), no
fallbacks; the agent compared as it is, the trial's fixes after. The Anthropic adapter is written
(`agent/anthropic_adapter.py`, chosen by model name in `agent/adapters.py`; the same contract as the OpenAI one,
append-only messages for the provider's thinking-block check, 402 `billing_error` as `OutOfCredit`; 15 tests with fake
clients and a whole D01 conversation, 19 of 19 planted bugs in scratchpad `planted_anthropic.py`). The owner's paid
check of the adapter (predictions in `docs/pilot/predictions.md`, "The comparison's second model"), part 1
(`runs/pilot-20261103T111614Z-claude-sonnet-5-5-low`, $1.90): D01-D65, stopped at D66 by a database connection
timeout (environment), 0 provider errors in 331 requests, 64 of 65 without a machine failure (D02: Sonnet said
104,90 for 104,80); the agent cost 4.6 times Sol a conversation, mostly cache writes of the shared instructions in
every conversation: the instructions are now marked for the cache (cost only, tested). Runners print each line at
once (Git Bash). Part 2 (`runs/pilot-20261103T122209Z-claude-sonnet-5-5-low`, D66-D89 with the cache mark, $0.395),
joined in `...-joined` (results in `docs/pilot/results.md`, "The comparison's second model"): 87/89 (D02 the amount
in the text, D85 a simulator fault), 0 unsafe, 0 provider errors in 455 requests, p95 8.2 s; agent $2.28, after the
mark 2.45 times Sol a conversation on the same scenarios (4.73 before; the rest is the model's: 1.65 times the input
tokens, twice the cache-read price, longer answers); 5 of 7 predictions right, 1 partly (D86 showed a note to
itself), 1 wrong (cost). Recorded, not repaired: amount slips (D02, D10 "8,990 BRL"), a card at once where the
customer asked to avoid one (D50, D58; Sol asked first), shortened unit IDs refused and corrected (D22, D50, D72).
Stopping rule held. The 39 converted (2026-11-03, plan change log): `scenarios/held-out-v1.3/` (split
`held_out_v1_3`) by `scripts/convert_held_out_v1_3.py`, each block checked against the selection manifest's SHA-256;
Olist orders by `uv run python -m refund_agent.olist v1.3` (`draw_tied`: up to four orders, the author's ties), 63
orders in `data/olist/subset-v1.3.json`; `conversion-log.md`; four decisions for the owner in `decision-notes.md`
(H421's card-and-boleto payment split from a real card payment, no Olist order has the pair; H422's "Siliconeoven"
kept; file names cut at 60 characters for the Windows path limit; author unit labels such as "(u2)" in 19 roles, a
limit). Free checks: 205 fidelity tests, policy checks agree with the code, a correct mocked conversation passes in all
39 and wrong ones fail (`tests/acceptance/test_held_out_v1_3_mock.py`), 12 of 12 planted file errors (scratchpad
`planted_v13_files.py`); the set lookups read every split from `SPLIT_DIRS`. Not frozen. Next: the owner approves the
files and the decisions, the freeze, targets, predictions, decision rule, the simulator choice, the final runner's
two configurations (Sol low, Sonnet low) with a budget cap, and the comparison run (about $2.60); then the handoff checks
and the five-person trial. Then Phase 7 (README, video, CI, licence) and a light test with 5 real users. 186/186 on
development shows only that the cases the rules were built on are solved. The user reads the step-C conversations in
`runs/pilot-20261027T144002Z-gpt-6-luna-none/user-review/`, 1 conversation of the D28 run and 5 of the confirmation run
(`user-review/`), 7 of the comparison
(`runs/pilot-20261023T201842Z-gpt-6.1-sol-low/user-review/`, four questions), 6 of the selection check run, and 10
of step 1 and 9 of each of steps 3, 2 and the repairs (`user-review/`); Claude's verdicts are shown after.
Development runs: Claude reads all, the user reads what Claude fails or notes. Phase 7 (video, code licence, external
test, CI on a remote) after v1.2.

## Environment

- Windows 11, Git Bash. Python with uv (as in Agent Action Guard); ruff, line length 120.
- Data: an Olist subset (Kaggle, "brazilian-ecommerce"), downloaded by the user; raw data stays out of git
  (`data/raw/`), with provenance and checksum. Mock mode must work with fully synthetic fixtures.
- Related project: `C:\Users\zosim\agent-action-guard` (approval gate bound to the exact call and used once, run
  manifests, metrics with intervals). Reuse ideas and code from it, but never edit it from here; it is being
  finished (release 0.3) in another session and its benchmark runs use the same OpenAI account.
