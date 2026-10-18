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

Phase 5 (§15) done and committed: review fixes, property tests (11 of 11 planted bugs), browser tests (10 of 10),
CI written but not run (no remote). Phase 6 preparation: the Olist subset (`refund_agent/olist.py`, `data/olist/`,
CC BY-NC-SA 4.0) and the twenty held-out scenarios built on it (`scenarios/held-out/`), reviewed by the user against
their closest development scenarios on 2026-10-18, not frozen yet; development scenarios stay synthetic (plan change
log). Next: the run before the freeze on the development set (`docs/pilot/predictions.md`, last section), the
user's dialogue audit, then the freeze (`scenarios/held-out/FROZEN`), quality targets, and the final evaluation
command. From now on nothing in the agent changes because of what the held-out scenarios ask.

## Environment

- Windows 11, Git Bash. Python with uv (as in Agent Action Guard); ruff, line length 120.
- Data: an Olist subset (Kaggle, "brazilian-ecommerce"), downloaded by the user; raw data stays out of git
  (`data/raw/`), with provenance and checksum. Mock mode must work with fully synthetic fixtures.
- Related project: `C:\Users\zosim\agent-action-guard` (approval gate bound to the exact call and used once, run
  manifests, metrics with intervals). Reuse ideas and code from it, but never edit it from here; it is being
  finished (release 0.3) in another session and its benchmark runs use the same OpenAI account.
