-- The customer's decline button is told to the agent like the cancel button (final evaluation of v1.1, 2026-10-26).
-- The customer declined proposal cards, the agent was told nothing, and seven times it said that a declined request
-- still waited for the customer's button. A decline now writes its notice in the same transaction, and the same
-- delivery hands it to the agent.
ALTER TABLE agent_notices DROP CONSTRAINT agent_notices_decision_check;
ALTER TABLE agent_notices ADD CONSTRAINT agent_notices_decision_check
    CHECK (decision IN ('approved', 'rejected', 'cancelled', 'declined'));
