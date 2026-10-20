# Product contract: Reliable Refund Agent v1

Status: frozen with the internal plan (version 4, 2026-10-09). Changes only because of running code, a failed test,
a measured cost or real feedback, logged with a date in the plan's change log. This page is a commitment, not a
result: until the tests and the evaluation report exist, nothing below has been shown to work.

## 1. Users and actors

| Actor | Can | Can never |
|---|---|---|
| Customer | See own orders, ask for a refund in chat, confirm or cancel a proposal, see status and receipt | See another customer's data, set the amount, approve |
| Staff member | Review the queue with trusted backend fields, approve or reject, take over a conversation | Approve what a hard policy rule forbids, edit a proposal |
| Agent (LLM) | Read the customer's orders and the policy, request a proposal, request execution, request a handoff | Confirm for the customer, approve, change roles, run SQL or code, act after a takeover |
| Backend | Decide: actor from the session, ownership, policy, amount, state transition and approval before any effect | |

The agent works inside the customer's session and never has more rights than the customer. The demo has one
fictional shop, 3-5 synthetic customers and one staff member.

## 2. The flow

1. The customer signs in and sees their orders, each with its number and items, and picks the item and quantity
   to refund; the chat opens with that selection. Describing the item or giving the order number in chat also
   works, and the agent asks when more than one item matches.
2. The agent retrieves the policy section; the citation is a real policy/section/version ID from the retriever.
3. The backend computes eligibility and amount and stores an immutable proposal. An ineligible request gets the
   policy reason (or a handoff for an exception) and no refund.
4. The customer confirms with a button on the proposal card. A "yes" typed in chat is not a confirmation.
5. A staff member approves or rejects it from the queue; a rejection gives the customer its reason.
6. `execute_refund(proposal_id)` asks the backend to execute; it commits one simulated refund and a receipt.
7. The customer sees the final state and its reason: refunded with receipt, rejected, cancelled or expired.

After a restart, a retry or an uncertain HTTP result (the client lost the answer and does not know whether the
refund happened), both screens show the stored backend state and the flow continues without a second effect.

Proposal states: `awaiting_customer_confirmation -> awaiting_staff_approval -> approved -> refunded`, with exits
`ineligible` (refused by the policy when created), `rejected`, `cancelled` (by the customer, before execution),
`expired` and `invalidated` (order or policy changed, replaced by a newer proposal, or handed to a person). The full
diagram, with the actor and checks of every transition, is in [state-machine.md](state-machine.md).

**Handoff.** When the customer asks for a person or the case is not covered (shipping refund, missing return,
policy exception), the agent records the reason and origin, the customer's goal, confirmed facts, any pending
proposal, past actions and the decision needed. The conversation becomes `human_controlled` at once, its open
proposals are invalidated, and the agent makes no further changes. Staff see and take the case in the console; there is no live staff-to-customer chat in v1.

## 3. v1 limits

- English only. One fictional shop, one currency: BRL, the currency of the Olist source data, as integer centavos.
- Every refund needs a customer confirmation and a staff approval. No automatic refunds.
- Money is simulated in a test ledger in local PostgreSQL and goes only to the original test payment record; the
  payee and bank details cannot change.
- Shipping is never refunded automatically (a person decides). Discounts are pre-allocated to order lines.
- Physical returns are not implemented. Where the policy needs the item back, `return_received` is trusted fixture
  data, never a claim by the customer or the model. Without it there is a request or a handoff, never a refund.
- The refund policy is fictional, not Olist's and not legal advice. Its numbers live in one controlled source and
  are not repeated here.
- Order history is a small checksummed Olist subset; accounts, approvals, current states and the ledger are
  synthetic. Mock mode uses fully synthetic fixtures and needs no API key.
- Local Docker Compose (backend, frontend, PostgreSQL). Screens refresh by polling.

## 4. Invariants

Tests, the evaluator and the authorization table refer to these IDs.

| ID | Invariant |
|---|---|
| INV-1 Ownership | A customer, and the agent in that customer's session, reads and changes only that customer's orders, conversations and proposals. Staff actions require the staff role. |
| INV-2 Server amounts | The backend computes every amount and quantity. Confirm and approve accept only a proposal ID and a decision; the actor comes from the session and the channel (customer screen, staff console, agent tool), and amounts or actors sent by the client or model are never used. |
| INV-3 Immutable proposal | A proposal binds customer, order, the IDs of the exact units, amount, currency, payment reference, policy version and hash, order version and expiry. Any change means a new proposal, confirmation and approval. |
| INV-4 Limits | Each unit is refunded at most once, for at most what was paid for it, across all proposals. The database enforces it with a unique constraint, in the same transaction as the idempotency key. |
| INV-5 Authorization | Every committed refund has one valid confirmation and one valid staff approval for that exact proposal, neither expired, rejected nor superseded. Approval never overrides a hard policy rule. |
| INV-6 At most once | One approval allows at most one committed operation. A retry returns the same receipt. The same idempotency key with a different payload is a conflict. |
| INV-7 Atomic commit | Checks, balance, approval use, operation, ledger lines, receipt, audit event and final state commit together or not at all. No transaction stays open while waiting for a model or a person. |
| INV-8 Human control | Every write checks `human_controlled` inside its transaction, so a call already in flight cannot write after a takeover. |
| INV-9 Audit | Append-only for the application role. Effects and their events share one commit; rejected attempts are recorded and survive rollback. |
| INV-10 Truthful status | Nothing says money was refunded before a committed receipt exists. Citations are retriever IDs, never model-written URLs. |

The promise is at most one committed effect and safe continuation, not general exactly-once: completing a refund
also needs the infrastructure to be available. Out of the threat model: a malicious database administrator. A staff
member can still be socially engineered; trusted fields reduce specific risks, they do not make people immune.

The evaluation's lab configuration C does not enforce confirmation, approval, time window, order state and
return-received inside `execute_refund`, to measure what backend enforcement changes; ownership, limits,
deduplication and audit stay enforced. It is loaded only by the isolated evaluation harness on a synthetic database
and is never a product or demo setting.

## 5. Done means

1. The flow works end to end in mock mode through both screens, including restart, retry and an uncertain HTTP
   result, with no API key.
2. Free CI tests on real PostgreSQL: policy and auth, the 15 required failure cases (races, crashes before and
   after commit, stale approvals, foreign data, invalid input, forged approvals, summary injection, evaluator
   negatives), property tests and critical browser tests.
3. The authorization table (about 15 direct calls, configurations A and C, checked in the database) has its expected
   values written before it runs; deviations are reported as findings.
4. 10 development and 20 held-out scenarios, held-out frozen and never used for tuning; after a final evaluation
   its held-out scenarios join the development set as copies, and a new claim needs new held-out scenarios. The evaluator is tested:
   correct outcomes pass; wrong amount or item, missing approval, duplicate refund, false completion and doing
   nothing fail.
5. Quality targets (success and pass^3 on legitimate flows) are committed after the pilot and before the final
   test. Fixed now: no observed unauthorized or duplicate committed write.
6. 180 conversations (20 held-out x 3 repeats x 3 configurations) within budget. The report gives denominators,
   pass^3, uncertainty, cost per correctly resolved case, every attempt and the simulator audit. A missed target is
   published with failure analysis, and the release is labelled accordingly.
7. Seed and reset, English README with threat model and limits, a 3-4 minute video, and a small external test with
   3-5 people (or a statement that it did not happen).

## 6. Out of scope for v1

Standalone shipment tracking and order cancellation; automatic refunds; real payment providers, store adapters,
warehouses or carriers; Greek; several shops, currencies or tax regimes; full helpdesk, omnichannel, voice or live
staff chat; public live demo, Kubernetes, workflow engines; multi-agent, MCP server, automatic tool creation,
long-term memory; training, fine-tuning, recommendations, leaderboard submissions.

Scope rule: a feature enters v1 only if another leaves or moves to v1.1. Ownership, approval binding, transactional
correctness and evaluator checks are never cut to save time.
