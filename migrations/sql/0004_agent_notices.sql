-- What the agent must still be told (outside review of 2026-10-15). A staff decision writes its notice in the same
-- transaction as the decision, so a server that stops before waking the agent loses nothing: the server delivers
-- pending notices after a decision, when it starts and every few seconds. The agent records the notice ID it applied,
-- so a second delivery, after a crash between the agent's run and the mark below, changes nothing. A delivery that
-- fails is tried again a few times only, so a failing model is not called without end.
CREATE TABLE agent_notices (
    id text PRIMARY KEY,
    conversation_id text NOT NULL REFERENCES conversations (id),
    proposal_id text NOT NULL REFERENCES proposals (id),
    decision text NOT NULL CHECK (decision IN ('approved', 'rejected')),
    created_at timestamptz NOT NULL,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    delivered_at timestamptz,
    last_error text
);
CREATE INDEX agent_notices_pending ON agent_notices (created_at) WHERE delivered_at IS NULL;

-- The application writes a notice and marks its delivery; it cannot delete one or change what it is about.
GRANT SELECT, INSERT ON agent_notices TO refund_app;
GRANT UPDATE (attempts, delivered_at, last_error) ON agent_notices TO refund_app;
