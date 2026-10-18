# Database schema

Status: implemented in [migrations/sql/0001_initial.sql](../migrations/sql/0001_initial.sql) and
[0002_sign_in.sql](../migrations/sql/0002_sign_in.sql), which are now the source for tables, columns, types,
constraints and privileges; this page keeps the reasons. One difference from the tables below: `order_units` has
no `product_id` and `seller_id` yet, because the synthetic fixtures have none; they come with the Olist import.
Statuses, transitions and the checks of each transition are in [state-machine.md](state-machine.md), generated from
code; the policy decisions are in `refund_agent/eligibility.py`.
Invariant IDs (INV-n) are those of the [product contract](product-contract.md).

## Conventions

- **Money:** `bigint` in minor units (centavos). A movement of money is `CHECK (amount_minor > 0)`. Currency is
  `char(3)`; the services check it equals the policy currency.
- **Time:** `timestamptz` in UTC, always taken from the backend's clock, which tests and the evaluation fix.
- **IDs:** UUIDs for rows the application creates; Olist IDs kept as text for imported data.
- **Trusted and untrusted text:** columns written by the model or typed by a person end in `_untrusted`. Screens show
  them labelled and as plain text, never as HTML, and they are never part of a content hash.
- **Two database roles:** the migration owner creates and owns the tables. The runtime role, which the application
  uses, gets only the privileges stated below. Permission tests run as the runtime role.
- **Who acts:** the backend takes the actor from the channel and the session, never from a request body. Confirm
  and cancel are endpoints of the customer screen, approve and reject of the staff console; none of them is an
  agent tool.

## Identity and conversations

| Table | Key columns | Constraints and reasons |
|---|---|---|
| `users` | `id`, `role` (customer, staff), `email`, `display_name`, `password_hash` | The password is checked with argon2 (argon2-cffi); only its hash is stored, and NULL means the user cannot sign in. The runtime role reads users but cannot change them. |
| `sessions` | `id` (SHA-256 of the cookie's random token), `user_id`, `csrf_token`, `created_at`, `expires_at`, `revoked_at` | In the database, so a session survives a restart and a sign-out ends it. Reading the table does not let anyone sign in. The runtime role may only add sessions and set `revoked_at`. Details in [http-api.md](http-api.md). |
| `conversations` | `id`, `customer_id`, `control` (agent, human_controlled), `created_at` | Every write about a conversation locks this row first (see below), so a handoff and an agent write are ordered (INV-8). |
| `messages` | `id`, `conversation_id`, `author` (customer, agent, staff, tool), `content_untrusted`, `created_at`, `seq` | The staff screen links model summaries back to these messages. `seq` comes from the audit log's own counter, so a message and an audit event (a proposal, a decision, a handoff) are in one exact order; the agent's messages are stored after each step of its run, before the tools of that step act. Times alone could not order them: the messages of one turn shared one time. |

LangGraph keeps its own checkpoint tables. They hold conversation state for resuming, never authority.

## Order facts (imported or synthetic; no agent tool writes them)

| Table | Key columns | Constraints and reasons |
|---|---|---|
| `orders` | `id`, `customer_id`, `status`, `purchased_at`, `delivered_at` (nullable), `material_version`, `source` (olist, synthetic) | `material_version` increases whenever status, delivery time, units, return records or payments change; a proposal binds it (INV-3). A missing or implausible `delivered_at` sends the case to a person (policy `eligible-orders`). |
| `order_units` | `id`, `order_id`, `unit_no`, `product_id`, `product_name`, `seller_id`, `price_minor`, `paid_minor`, `shipping_minor`, `received_back_at` (nullable) | **One row per unit**, as Olist stores order items (`order_item_id` is `unit_no`); unique (`order_id`, `unit_no`). `CHECK (0 <= paid_minor AND paid_minor <= price_minor)`. `paid_minor` is fixed once when the order is recorded (a total over identical units is split with `split_paid()`) and never recalculated. `received_back_at` is trusted return data from fixtures or staff, never set from a chat. The screens group identical units by product. |
| `payments` | `id`, `order_id`, `sequential`, `method`, `installments`, `amount_minor` | Automatic refunds need exactly one payment record with a known method and a positive amount (policy `payment`). Instalments are a column of one record, not separate records; to be confirmed on the real Olist import. |

## Refund state

| Table | Key columns | Constraints and reasons |
|---|---|---|
| `proposals` | `id`, `request_key` (unique), `request_hash`, `conversation_id`, `customer_id`, `order_id`, `payment_id`, `amount_minor`, `currency`, `policy_version`, `policy_hash`, `order_material_version`, `status`, `status_reason`, `reasons`, `created_at`, `expires_at`, `content_hash`, `created_xact`, `summary_untrusted` | Only valid requests by the order's owner are stored, including the ones the policy refuses (`ineligible`, with `reasons` as policy section IDs); a foreign order or invalid input is a rejected attempt in the audit log, not a proposal. Partial unique index on `conversation_id` where status is one of the open statuses (`awaiting_customer_confirmation`, `awaiting_staff_approval`, `approved`): at most one open proposal per conversation. The runtime role may update only `status` and `status_reason`, so the bound content cannot change (INV-3). |
| `proposal_units` | `proposal_id`, `order_unit_id`, `amount_minor` | PK (`proposal_id`, `order_unit_id`). The runtime role has `SELECT` and `INSERT` only, and a trigger allows the insert only in the transaction that created the proposal (`created_xact = pg_current_xact_id()`): lines cannot be added, changed or removed later. The proposal's `content_hash` covers them. |
| `customer_confirmations` | `id`, `proposal_id` (unique), `customer_id`, `decision` (confirmed, declined), `content_hash`, `decided_at` | One decision per proposal, for its exact content (INV-5). |
| `staff_decisions` | `id`, `proposal_id` (unique), `staff_id`, `decision` (approved, rejected), `content_hash`, `decided_at` | One decision per proposal, for its exact content (INV-5). Also unique (`id`, `proposal_id`, `decision`), the target of the foreign key below. |
| `refund_operations` | `id`, `proposal_id` (NOT NULL, unique), `approval_id` (nullable, unique), `approval_decision`, `idempotency_key` (unique), `request_hash`, `amount_minor`, `currency`, `payment_id`, `receipt_number` (unique), `receipt`, `committed_at` | Unique `proposal_id`: a proposal is executed at most once, in every configuration, with or without an approval (PostgreSQL allows many NULLs under a unique constraint, so unique `approval_id` alone would not do it). Unique `approval_id`: an approval is used at most once (INV-6). Foreign key (`approval_id`, `proposal_id`, `approval_decision`) to `staff_decisions` (`id`, `proposal_id`, `decision`) with `CHECK (approval_decision = 'approved')`: the database itself proves the approval is an approval of this very proposal. `approval_id` is nullable only so configuration C can run; in A the service requires it and the evaluator checks it. `receipt` is the receipt as returned at commit, returned unchanged on every retry, also after expiry. The runtime role cannot update or delete these rows. |
| `ledger_lines` | `id`, `operation_id`, `order_unit_id` (unique), `amount_minor`, `currency`, `payment_id` | Unique `order_unit_id`: **a unit can be refunded only once**, enforced by the database in every configuration (INV-4). `CHECK (amount_minor > 0)`; each line's amount equals the unit's `paid_minor`, and an operation's lines add up to its amount (checked in the transaction and again by the evaluator). The runtime role cannot update or delete them. |

## Audit and handoff

| Table | Key columns | Constraints and reasons |
|---|---|---|
| `audit_events` | `id` (bigserial), `at`, `actor_type`, `actor_id`, `conversation_id`, `proposal_id`, `operation_id`, `event`, `outcome` (committed, rejected), `reason`, `details` | The runtime role has `INSERT` and `SELECT` only (INV-9). A committed effect and its event share one transaction; a rejected attempt is written in a new transaction after the rollback. |
| `agent_notices` | `id` (`notice-` and the staff decision's ID), `conversation_id`, `proposal_id`, `decision`, `created_at`, `attempts`, `delivered_at`, `last_error` | Written in the staff decision's transaction, so the agent is told even if the server stops right after it; delivered after the decision, at start and every few seconds, marked delivered after the agent's run, and tried at most three times. The agent records the notice ID it applied, so a second delivery changes nothing. The runtime role may add a notice and set `attempts`, `delivered_at` and `last_error` only. |
| `handoffs` | `id`, `conversation_id`, `origin` (customer, agent, staff), `reason`, `created_at`, `pending_proposal_id`, `prior_actions`, `customer_goal_untrusted`, `confirmed_facts_untrusted`, `decision_needed_untrusted`, `status` (open, taken), `taken_by`, `taken_at` | Created in the same transaction that sets `control = human_controlled` and invalidates the open proposals. `prior_actions` comes from the audit log, so it is trusted. |

## Transactions

Every write that concerns a conversation (propose, confirm, cancel, approve, reject, execute, hand-off) starts by
locking rows in one fixed order: the conversation, then the proposal. Using the same order everywhere means two
transactions can never wait for each other forever (deadlock), and it orders a handoff and an agent write: once
the handoff commits, every later agent write fails `agent_in_control`; if the refund committed first, it stays
`refunded`. No transaction stays open while waiting for a model or a person (INV-7).

**Propose.** Lock the conversation. If its open proposal is out of date (clock at or past `expires_at`, or a
changed order or policy version), close it first as `expired` or `invalidated`, so a stale row never blocks a new
proposal. Run the checks of `propose`, store the proposal and its units, supersede an unconfirmed open proposal if
the new one is eligible, write the audit event, commit.

**Execute (configuration A).**

1. Lock the conversation, then the proposal.
2. `actor_owns`: the session's customer owns them. Otherwise refuse without revealing anything.
3. If the idempotency key exists: the same `request_hash` returns the stored receipt; a different one is a conflict.
4. If the proposal already has an operation, return its stored receipt, whatever the proposal's age.
5. Run the remaining checks of the `execute` transition, in their listed order.
6. Insert the operation with its receipt, one ledger line per unit, and the audit event, and set the status to
   `refunded`. The unique `order_unit_id` makes the check that a unit is still unrefunded and the write one atomic
   step: if another transaction refunded a unit first, the insert fails and nothing is committed.
7. Commit. On any failure: roll back, then record the rejected attempt in a new transaction.

## Expiry and invalidation

Nothing runs in the background. Every action that touches a proposal first compares the clock with `expires_at`
(the action is allowed only strictly before it), and the bound order and policy versions with the current ones. If
the proposal is out of date, the same transaction moves it to `expired` or `invalidated`, records why, and refuses
the action. A refunded proposal is final: expiry never hides a completed refund or its receipt.

## Acceptance tests for phase 2

They need a real PostgreSQL. Each states its expected outcome by hand, without reading `refund_agent.states` or
`refund_agent.eligibility` (enforced by `tests/test_independence.py`).

1. Commit, crash before the response, clock moves 72 hours, retry: the same receipt, one operation, one ledger line
   per unit.
2. Retry with another customer's session and the same idempotency key: no receipt, a rejected attempt in the audit.
3. Handoff and execute race with barriers on separate connections: either `refunded` and nothing to invalidate, or
   `invalidated` and no operation; never both.
4. The same execute call on an unconfirmed proposal in A and in C: A refuses with no operation and no ledger
   lines; C commits them and the evaluator reports an unauthorized committed action.
5. In C, two executions of one proposal with different idempotency keys and no approval: one operation.
6. Two proposals, in two conversations, for the same unit, both approved: one refund; the second fails on the
   unique ledger line.
7. Two proposals for different units of the same product: both refund.
8. A new proposal after the open one expired: allowed, and the old one is marked `expired` in the same transaction.
9. As the runtime role: no update of proposal content, no insert of proposal units after creation, no update or
   delete of proposal units, operations, ledger lines or audit events.
10. An approval of proposal X attached to an operation of proposal Y: rejected by the foreign key.
11. Confirm or cancel sent through the agent's tool executor, or with an actor in the request body: refused.
12. Propose for a foreign order: no proposal row, a rejected attempt in the audit.

## Out of this schema

Evaluation run manifests and traces are files, not tables. Configuration C uses the same schema on its own
synthetic database.
