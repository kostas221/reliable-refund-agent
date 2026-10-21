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
Step 2 ready (approved 2026-10-21, plan change log): `assess_refund` (read-only, the decision of `propose` with its
facts) in place of the policy search; an eligible result cites the amount section; `execute_refund` with no arguments
pays the conversation's latest request the policy did not refuse; `customer_asked` needs the customer's own words, found
in a customer message; instructions v6 = v5 with three changes. Predictions in `docs/pilot/predictions.md`, with floors
for what step 3 gained; the user commits and runs the batch. If D09 and D17 still do not ask first, the next change is
the order of the instructions, measured on its own. Development runs: Claude reads all, the user reads what Claude fails
or notes. Phase 7 (video, code licence, external test, CI on a remote) after v1.1.

## Environment

- Windows 11, Git Bash. Python with uv (as in Agent Action Guard); ruff, line length 120.
- Data: an Olist subset (Kaggle, "brazilian-ecommerce"), downloaded by the user; raw data stays out of git
  (`data/raw/`), with provenance and checksum. Mock mode must work with fully synthetic fixtures.
- Related project: `C:\Users\zosim\agent-action-guard` (approval gate bound to the exact call and used once, run
  manifests, metrics with intervals). Reuse ideas and code from it, but never edit it from here; it is being
  finished (release 0.3) in another session and its benchmark runs use the same OpenAI account.
