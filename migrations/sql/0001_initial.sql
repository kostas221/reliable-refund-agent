-- Initial schema. The source of truth for tables, constraints and privileges; docs/schema.md keeps the reasons.
-- Runs as refund_owner, which owns every table. The application connects as refund_app and gets only the
-- privileges granted at the end of this file.

-- Identity and conversations

CREATE TABLE users (
    id text PRIMARY KEY,
    role text NOT NULL CHECK (role IN ('customer', 'staff')),
    email text NOT NULL UNIQUE,
    display_name text NOT NULL
);

CREATE TABLE conversations (
    id text PRIMARY KEY,
    customer_id text NOT NULL REFERENCES users (id),
    -- Read inside every agent write's transaction (INV-8).
    control text NOT NULL DEFAULT 'agent' CHECK (control IN ('agent', 'human_controlled')),
    created_at timestamptz NOT NULL
);

CREATE TABLE messages (
    id text PRIMARY KEY,
    conversation_id text NOT NULL REFERENCES conversations (id),
    author text NOT NULL CHECK (author IN ('customer', 'agent', 'staff', 'tool')),
    content_untrusted text NOT NULL,
    created_at timestamptz NOT NULL
);

-- Order facts: written by the import or the fixture loader, read-only for the application

CREATE TABLE orders (
    id text PRIMARY KEY,
    customer_id text NOT NULL REFERENCES users (id),
    status text NOT NULL CHECK (
        status IN ('created', 'approved', 'invoiced', 'processing', 'shipped', 'delivered', 'canceled', 'unavailable')
    ),
    purchased_at timestamptz NOT NULL,
    delivered_at timestamptz,
    -- Increases whenever a fact a proposal depends on changes; a proposal binds it (INV-3).
    material_version integer NOT NULL DEFAULT 1 CHECK (material_version >= 1),
    source text NOT NULL CHECK (source IN ('olist', 'synthetic')),
    seller_message_untrusted text NOT NULL DEFAULT ''
);

-- One row per unit, as Olist stores order items.
CREATE TABLE order_units (
    id text PRIMARY KEY,
    order_id text NOT NULL REFERENCES orders (id),
    unit_no integer NOT NULL CHECK (unit_no >= 1),
    product_name text NOT NULL,
    price_minor bigint NOT NULL CHECK (price_minor >= 0),
    -- Fixed once when the order is recorded; never more than the price.
    paid_minor bigint NOT NULL CHECK (paid_minor >= 0 AND paid_minor <= price_minor),
    shipping_minor bigint NOT NULL CHECK (shipping_minor >= 0),
    received_back_at timestamptz,
    UNIQUE (order_id, unit_no)
);

CREATE TABLE payments (
    id text PRIMARY KEY,
    order_id text NOT NULL REFERENCES orders (id),
    sequential integer NOT NULL CHECK (sequential >= 1),
    method text NOT NULL,
    installments integer NOT NULL DEFAULT 1 CHECK (installments >= 1),
    amount_minor bigint NOT NULL CHECK (amount_minor >= 0),
    UNIQUE (order_id, sequential)
);

-- Refund state

CREATE TABLE proposals (
    id text PRIMARY KEY,
    request_key text NOT NULL UNIQUE,
    request_hash text NOT NULL,
    conversation_id text NOT NULL REFERENCES conversations (id),
    customer_id text NOT NULL REFERENCES users (id),
    order_id text NOT NULL REFERENCES orders (id),
    payment_id text REFERENCES payments (id),
    amount_minor bigint NOT NULL CHECK (amount_minor >= 0),
    currency char(3) NOT NULL,
    policy_version text NOT NULL,
    policy_hash text NOT NULL,
    order_material_version integer NOT NULL,
    status text NOT NULL CHECK (
        status IN (
            'awaiting_customer_confirmation', 'awaiting_staff_approval', 'approved', 'refunded',
            'ineligible', 'rejected', 'cancelled', 'expired', 'invalidated'
        )
    ),
    status_reason text,
    reasons text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    content_hash text NOT NULL,
    -- Set by the database, never by the application (no INSERT privilege on it): the transaction that created
    -- the proposal, the only one allowed to add its units.
    created_xact xid8 NOT NULL DEFAULT pg_current_xact_id(),
    summary_untrusted text NOT NULL DEFAULT '',
    CHECK (status <> 'ineligible' OR cardinality(reasons) > 0)
);

-- At most one open proposal per conversation.
CREATE UNIQUE INDEX one_open_proposal_per_conversation ON proposals (conversation_id)
    WHERE status IN ('awaiting_customer_confirmation', 'awaiting_staff_approval', 'approved');

CREATE TABLE proposal_units (
    proposal_id text NOT NULL REFERENCES proposals (id),
    order_unit_id text NOT NULL REFERENCES order_units (id),
    amount_minor bigint NOT NULL CHECK (amount_minor >= 0),
    PRIMARY KEY (proposal_id, order_unit_id)
);

-- A proposal's units can be added only by the transaction that created it (INV-3).
CREATE FUNCTION proposal_units_only_at_creation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT created_xact FROM proposals WHERE id = NEW.proposal_id) IS DISTINCT FROM pg_current_xact_id() THEN
        RAISE EXCEPTION 'proposal units can be added only in the transaction that created the proposal';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER proposal_units_only_at_creation BEFORE INSERT ON proposal_units
    FOR EACH ROW EXECUTE FUNCTION proposal_units_only_at_creation();

CREATE TABLE customer_confirmations (
    id text PRIMARY KEY,
    proposal_id text NOT NULL UNIQUE REFERENCES proposals (id),
    customer_id text NOT NULL REFERENCES users (id),
    decision text NOT NULL CHECK (decision IN ('confirmed', 'declined')),
    content_hash text NOT NULL,
    decided_at timestamptz NOT NULL
);

CREATE TABLE staff_decisions (
    id text PRIMARY KEY,
    proposal_id text NOT NULL UNIQUE REFERENCES proposals (id),
    staff_id text NOT NULL REFERENCES users (id),
    decision text NOT NULL CHECK (decision IN ('approved', 'rejected')),
    content_hash text NOT NULL,
    decided_at timestamptz NOT NULL,
    UNIQUE (id, proposal_id, decision)
);

CREATE SEQUENCE receipt_numbers;

CREATE TABLE refund_operations (
    id text PRIMARY KEY,
    -- A proposal is executed at most once, in every configuration, with or without an approval.
    proposal_id text NOT NULL UNIQUE REFERENCES proposals (id),
    -- An approval is used at most once (INV-6). Nullable only so that configuration C can run.
    approval_id text UNIQUE,
    approval_decision text CHECK (approval_decision = 'approved'),
    idempotency_key text NOT NULL UNIQUE,
    request_hash text NOT NULL,
    amount_minor bigint NOT NULL CHECK (amount_minor > 0),
    currency char(3) NOT NULL,
    payment_id text NOT NULL REFERENCES payments (id),
    receipt_number text NOT NULL UNIQUE,
    -- Stored at commit and returned unchanged on every retry, also after expiry.
    receipt jsonb NOT NULL,
    committed_at timestamptz NOT NULL,
    CHECK ((approval_id IS NULL) = (approval_decision IS NULL)),
    -- The database itself proves that the approval is an approval of this very proposal.
    FOREIGN KEY (approval_id, proposal_id, approval_decision)
        REFERENCES staff_decisions (id, proposal_id, decision)
);

CREATE TABLE ledger_lines (
    id text PRIMARY KEY,
    operation_id text NOT NULL REFERENCES refund_operations (id),
    -- A unit can be refunded only once, in every configuration (INV-4).
    order_unit_id text NOT NULL UNIQUE REFERENCES order_units (id),
    amount_minor bigint NOT NULL CHECK (amount_minor > 0),
    currency char(3) NOT NULL,
    payment_id text NOT NULL REFERENCES payments (id)
);

-- Audit and handoff

CREATE TABLE audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at timestamptz NOT NULL,
    actor_type text NOT NULL CHECK (actor_type IN ('customer', 'agent', 'staff', 'system')),
    actor_id text,
    -- No foreign keys: a rejected attempt may name rows that do not exist or belong to someone else.
    conversation_id text,
    proposal_id text,
    operation_id text,
    event text NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('committed', 'rejected')),
    reason text,
    details jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE handoffs (
    id text PRIMARY KEY,
    conversation_id text NOT NULL REFERENCES conversations (id),
    origin text NOT NULL CHECK (origin IN ('customer', 'agent', 'staff')),
    reason text NOT NULL,
    created_at timestamptz NOT NULL,
    pending_proposal_id text REFERENCES proposals (id),
    prior_actions jsonb NOT NULL DEFAULT '[]',
    customer_goal_untrusted text NOT NULL DEFAULT '',
    confirmed_facts_untrusted text NOT NULL DEFAULT '',
    decision_needed_untrusted text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'taken')),
    taken_by text REFERENCES users (id),
    taken_at timestamptz
);

-- Privileges of the application role. Everything not granted here is refused by the database.

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO refund_app;

GRANT SELECT ON users, orders, order_units, payments TO refund_app;
GRANT SELECT, INSERT ON conversations, messages, customer_confirmations, staff_decisions,
    refund_operations, ledger_lines, audit_events, handoffs, proposal_units TO refund_app;
GRANT UPDATE (control) ON conversations TO refund_app;
GRANT SELECT ON proposals TO refund_app;
GRANT INSERT (
    id, request_key, request_hash, conversation_id, customer_id, order_id, payment_id, amount_minor, currency,
    policy_version, policy_hash, order_material_version, status, status_reason, reasons, created_at, expires_at,
    content_hash, summary_untrusted
) ON proposals TO refund_app;
GRANT UPDATE (status, status_reason) ON proposals TO refund_app;
GRANT UPDATE (status, taken_by, taken_at) ON handoffs TO refund_app;
GRANT USAGE ON SEQUENCE receipt_numbers TO refund_app;
