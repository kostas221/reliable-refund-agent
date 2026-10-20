# Reliable Refund Agent

A customer-support agent that handles refund requests for a fictional online shop, and actually pays them, into a
test ledger, under one guarantee: no refund is paid without the customer's confirmation and a staff member's
approval of that exact proposal, and no refund is paid twice. The project shows how to let a language model take an
action with real consequences safely, and how to prove that it does.

It runs on your own computer: a chat screen for the customer, a console for the staff member, a backend with a
PostgreSQL database, and the agent between them. It is a portfolio project and a reference design, not a hosted
service.

> **Status, 2026-10-20: v1 met its safety requirement and missed both quality targets.** On twenty frozen held-out
> scenarios, no refund was paid without authorization or twice (0 of 180 conversations); the agent succeeded in 41
> of 60 conversations (target 51) and in all three tries of 11 of 20 scenarios (target 14). The causes and the next
> version are in [docs/final/results.md](docs/final/results.md). The video and the code licence will be added here.

## What happens in one refund

1. **The customer asks in the chat:** "I sent back the blue mug, it arrived chipped. Can I get a refund?"
2. **The agent looks up the customer's own orders** and asks the backend for a refund proposal for the mug. The
   backend, not the model, decides whether the policy allows it and computes the amount: R$ 49,90.
3. **The customer confirms with a button** on the proposal card. A "yes" typed in the chat confirms nothing.
4. **A staff member approves or rejects it** in the console, seeing the backend's figures apart from anything the
   model wrote. A rejection needs a reason, which the customer is shown.
5. **The agent asks the backend to pay.** One transaction checks everything again, writes the refund to the ledger
   and returns a receipt; asking again returns the same receipt.

When the policy refuses (too late, not returned yet, already refunded), the agent says why and cites the policy
section. When a case needs a person, or the customer asks for one, the agent hands the conversation over and makes
no further changes.

## Why it can be trusted with money

The model proposes; the backend decides. The design rests on a few rules, each enforced in code and tested:

- **The backend is the authority.** The model's tools take only IDs and text. Ownership, the refund policy, the
  amount, the state of the request and the approval are checked by the backend's services, in the same database
  transaction that pays.
- **An approval is bound to one exact proposal and used once.** A changed order, an expired proposal or a second
  attempt cannot reuse it. Unique constraints in the database stop a unit being refunded twice, even under races.
- **Nothing the model writes grants anything.** Confirmation is the customer's button and approval is the staff
  member's action. Text from sellers, customers or the model is marked as untrusted wherever it is shown.
- **A crash or a lost answer does not repeat a payment.** Every request carries an idempotency key; a retry after a
  crash returns the stored receipt.

## How it is evaluated

| Evidence | What it shows | Where |
|---|---|---|
| 15 failure cases | Races, crashes before and after the commit, stale approvals, forged approvals, foreign data, a restart with a pending approval | [docs/failure-cases.md](docs/failure-cases.md) |
| Authorization table, 20 cases | A forbidden call, made directly, in configurations A (all checks) and C (selected checks off), checked in the database | [docs/authorization-table.md](docs/authorization-table.md) |
| Property tests | Random sequences of actions by every party never break the invariants; planted bugs are caught | [docs/failure-cases.md](docs/failure-cases.md) |
| Browser tests | The two screens, by keyboard and mouse, through a refund, a restart, a lost answer and a rejection | [docs/screens.md](docs/screens.md) |
| 30 scenarios with a simulated customer | 10 development scenarios used to build the agent; 20 held-out scenarios, frozen on 2026-10-19, never used for tuning and run once, in the final evaluation of v1, on real Olist orders. Since then they are also development scenarios, as copies | [docs/scenarios.md](docs/scenarios.md) |
| Final evaluation | The held-out scenarios, three tries each, in three configurations: the product (A), a stronger model (B), and the product's model with the selected checks off (C) | [docs/final/README.md](docs/final/README.md) |

Each conversation is judged from the database, not from what the agent says, and then read: Claude reads every
conversation and the user reads a fixed share without Claude's verdicts. The targets were written before the final
run: no unauthorized or duplicate refund, task success of at least 85% and pass^3 of at least 70%
([docs/quality-targets.md](docs/quality-targets.md)); the predictions are in
[docs/final/predictions.md](docs/final/predictions.md).

The evaluation is inspired by τ-bench, extended with application-level authorization, persistent approvals, failure
recovery and adversarial scenarios.

## Results of the final evaluation

| | A: the product | B: a stronger model | C: checks off |
|---|---|---|---|
| Conversations that succeeded (target for A: 51 of 60) | 41 of 60 | 50 of 60 | 40 of 60 |
| Scenarios that succeeded in all three tries (target for A: 14 of 20) | 11 of 20 | 15 of 20 | 10 of 20 |
| Refunds paid without authorization, or twice | 0 | 0 | 0 |
| Agent cost per resolved case | $0.0006 | $0.0103 | $0.0006 |

The guarantee held in every conversation, including the attacks: a false manager, instructions hidden in a message,
a request for another customer's data and a refund to another card. The targets were missed for reasons the
saved conversations show:

- **The policy search.** The agent never cited a section its policy search had not returned, and that search missed
  sections a customer's question needed. The policy is short enough to give the agent in full.
- **The handoff rule.** The policy sends any request for an exception to a person, so the agent handed off requests
  the scenarios expected it to refuse.
- **Wrong reasons and missing questions.** In a few conversations the agent gave a true reason that was not the one
  that decides, or proposed one of two matching items without asking which.

Nothing was tuned on the held-out set; the fixes go into a next version measured on new held-out scenarios. Every
failed conversation, the comparisons with their intervals, and the predictions against the results are in
[docs/final/results.md](docs/final/results.md).

## Run it

You need Docker, [uv](https://docs.astral.sh/uv/) and Node.js. Mock mode needs no API key: a scripted agent plays
one development scenario.

```bash
docker compose up -d
uv run python -m refund_agent.api
```

In a second terminal:

```bash
cd frontend && npm ci && npm run dev
```

Open http://localhost:5173 and sign in as the customer or the staff member the server prints; the demo password is in
`refund_agent/api/__main__.py`. `--scenario D04` loads another development scenario. More in
[docs/screens.md](docs/screens.md).

The tests, about 750 of them, run on the local database:

```bash
REQUIRE_DB=1 uv run pytest -q
```

## Where things are

| Path | What it holds |
|---|---|
| `refund_agent/refunds.py` | The domain services: propose, confirm, decide, execute, cancel, hand off |
| `refund_agent/agent/` | The agent: graph, tools, model adapters, budget, notices |
| `refund_agent/api/` and `frontend/` | The HTTP layer and the two screens |
| `refund_agent/evaluation/` | Runner, evaluator, dialogue audit, pilot, final evaluation and its report |
| `scenarios/` | The development and held-out scenarios |
| `docs/` | Product contract, policy, schema, state machine, plan and results |

## Limits

- One fictional shop, one currency (BRL), English only, and a simulated ledger: no real payment provider.
- Local only. There is no public deployment, and no live chat between staff and customer.
- Twenty held-out scenarios, three tries each: the intervals are wide, and a result holds for these scenarios, not
  for every shop.
- The simulated customer is a model of the same family as the agent. Claude read every conversation; a person read a
  share of them, blind to Claude's verdicts but helped by another model.
- Language models are not deterministic: a new run with the same settings can answer differently. The reports are
  reproducible from the saved results.

## Data and licences

The held-out orders are drawn from the Olist Brazilian e-commerce dataset, licensed CC BY-NC-SA 4.0
([data/olist/README.md](data/olist/README.md)). The code's licence has not been chosen yet.
