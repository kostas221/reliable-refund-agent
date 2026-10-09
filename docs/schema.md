# Database schema (design for phase 2)

Status: design, not yet a migration. When the first Alembic migration exists, it becomes the source for columns and
types, and this page keeps only the reasons. Statuses, transitions and the checks of each transition are in
[state-machine.md](state-machine.md), generated from code. Invariant IDs (INV-n) are those of the
[product contract](product-contract.md).

## Conventions

- **Money:** `bigint` in minor units (centavos). A movement of money is `CHECK (amount_minor > 0)`. Currency is
  `char(3)`; the services check it equals the policy currency.
- **Time:** `timestamptz` in UTC, always taken from the backend's clock, which tests and the evaluation fix.
- **IDs:** UUIDs for rows the application creates; Olist IDs kept as text for imported data.
- **Trusted and untrusted text:** columns written by the model or typed by a person end in `_untrusted`. Screens show
  them labelled and as plain text, never as HTML, and they are never part of a content hash.

## Identity and conversations

| Table | Key columns | Constraints and reasons |
|---|---|---|
| `users` | `id`, `role` (customer, staff), `email`, `display_name` | Sessions use an established library, not our own authentication. |
| `conversations` | `id`, `customer_id`, `control` (agent, human_controlled), `created_at` | `control` is read inside every agent write's transaction (INV-8). |
| `messages` | `id`, `conversation_id`, `author` (customer, agent, staff, tool), `content_untrusted`, `created_at` | The staff screen links model summaries back to these messages. |

LangGraph keeps its own checkpoint tables. They hold conversation state for resuming, never authority.

## Order facts (imported or synthetic; no agent tool writes them)

| Table | Key columns | Constraints and reasons |
|---|---|---|
| `orders` | `id`, `customer_id`, `status`, `purchased_at`, `delivered_at`, `material_version`, `source` (olist, synthetic) | `material_version` increases whenever status, delivery time, lines, received-back units or payments change. A proposal binds it (INV-3). |
| `order_lines` | `id`, `order_id`, `product_id`, `product_name`, `quantity`, `unit_price_minor`, `discount_minor`, `paid_minor`, `shipping_minor`, `received_back_quantity`, `source_item_ids` | `CHECK (paid_minor = quantity * unit_price_minor - discount_minor AND paid_minor >= 0)`, `CHECK (received_back_quantity BETWEEN 0 AND quantity)`. Olist stores one row per unit; identical units (same product, seller and price) become one line with a quantity, and the Olist `order_item_id`s stay in `source_item_ids`. |
| `payments` | `id`, `order_id`, `sequential`, `type`, `amount_minor` | The policy hands orders with more than one payment record to a person. |

## Refund state

| Table | Key columns | Constraints and reasons |
|---|---|---|
| `refund_balances` | `order_line_id` (PK), `remaining_quantity`, `remaining_minor` | `CHECK (remaining_quantity >= 0 AND remaining_minor >= 0)`. Starts at the line's `quantity` and `paid_minor`. Only the execute transaction changes it, with a conditional `UPDATE` (INV-4). |
| `proposals` | `id`, `request_key` (unique), `request_hash`, `conversation_id`, `customer_id`, `order_id`, `payment_id`, `amount_minor`, `currency`, `policy_version`, `order_material_version`, `status`, `status_reason`, `ineligible_reasons`, `created_at`, `expires_at`, `content_hash`, `summary_untrusted` | Partial unique index on `conversation_id` where status is open: at most one open proposal per conversation. The application role may update only `status` and `status_reason` (column privileges), so the bound content cannot change (INV-3). `ineligible_reasons` are policy section IDs. |
| `proposal_lines` | `proposal_id`, `order_line_id`, `quantity`, `amount_minor`, `expected_remaining_quantity`, `expected_remaining_minor` | PK (`proposal_id`, `order_line_id`), `CHECK (quantity > 0)`. The `expected_*` values are the line balance the quote saw; execution requires them unchanged, so concurrent proposals cannot leave rounding centavos behind. |
| `customer_confirmations` | `id`, `proposal_id` (unique), `customer_id`, `decision` (confirmed, declined), `content_hash`, `decided_at` | One decision per proposal. `content_hash` must equal the proposal's (INV-5). |
| `staff_decisions` | `id`, `proposal_id` (unique), `staff_id`, `decision` (approved, rejected), `content_hash`, `decided_at` | One decision per proposal, bound to the exact content (INV-5). |
| `refund_operations` | `id`, `proposal_id` (unique), `approval_id` (unique, nullable), `idempotency_key` (unique), `request_hash`, `amount_minor`, `currency`, `payment_id`, `receipt_number` (unique), `committed_at` | Unique `approval_id`: one approval allows at most one operation, enforced by the database (INV-6). It is nullable only so that configuration C can run; in A the service requires it and the evaluator checks it. The receipt is these columns: a separate one-to-one table would add nothing. |
| `ledger_lines` | `id`, `operation_id`, `order_line_id`, `quantity`, `amount_minor`, `currency`, `payment_id` | `CHECK (amount_minor > 0)`. An operation's lines add up to its amount, checked in the transaction and again by the evaluator. |

## Audit and handoff

| Table | Key columns | Constraints and reasons |
|---|---|---|
| `audit_events` | `id` (bigserial), `at`, `actor_type`, `actor_id`, `conversation_id`, `proposal_id`, `operation_id`, `event`, `outcome` (committed, rejected), `reason`, `details` | The application role has `INSERT` and `SELECT` only (INV-9). A committed effect and its event share one transaction; a rejected attempt is written in a new transaction after the rollback. |
| `handoffs` | `id`, `conversation_id`, `origin` (customer, agent, staff), `reason`, `created_at`, `pending_proposal_id`, `prior_actions`, `customer_goal_untrusted`, `confirmed_facts_untrusted`, `decision_needed_untrusted`, `status` (open, taken), `taken_by`, `taken_at` | Created in the same transaction that sets `control = human_controlled` and invalidates the open proposals. `prior_actions` comes from the audit log, so it is trusted. |

## The execute transaction (configuration A)

1. Begin. Lock rows in one fixed order: conversation, then proposal, then balance rows by ascending
   `order_line_id`. Every transaction that touches these rows uses the same order, so two of them can never wait
   for each other forever (deadlock).
2. If the idempotency key exists: same `request_hash` returns the stored receipt; a different one is a conflict.
3. If the proposal already has an operation, return its receipt.
4. Run the checks of the `execute` transition in [state-machine.md](state-machine.md).
5. For each line, a conditional update in the style of the plan (section 6), with the exact-balance condition:

   ```sql
   UPDATE refund_balances
   SET remaining_quantity = remaining_quantity - :quantity,
       remaining_minor = remaining_minor - :amount
   WHERE order_line_id = :order_line_id
     AND remaining_quantity = :expected_remaining_quantity
     AND remaining_minor = :expected_remaining_minor
     AND :quantity > 0 AND :amount > 0
     AND remaining_quantity >= :quantity
     AND remaining_minor >= :amount
   RETURNING remaining_quantity, remaining_minor;
   ```

   No row returned means the refund is not allowed: roll back.
6. Insert the operation with its receipt, the ledger lines and the audit event, and set the status to `refunded`.
   Commit.
7. On any failure: roll back, then record the rejected attempt in a new transaction.

No model call and no wait for a person happens inside this transaction (INV-7). Confirm, approve, cancel and
hand-off follow the same pattern: lock, check, write the decision, the status and the audit event, commit.

## Expiry and invalidation

Nothing runs in the background. Every action that touches a proposal first compares the clock with `expires_at`,
and the bound order and policy versions with the current ones. If the proposal is out of date, the same
transaction moves it to `expired` or `invalidated`, records why, and refuses the action. Screens show the status
the backend computes on read.

## Out of this schema

Evaluation run manifests and traces are files, not tables. Configuration C uses the same schema on its own
synthetic database.
