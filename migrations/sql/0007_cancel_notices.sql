-- The customer's cancellation is told to the agent like a staff decision (review of the model comparison,
-- 2026-10-24). In D28 the customer cancelled with the button before the staff decision and the agent was told
-- nothing: it answered "if you haven't already, use the cancel button", and later that its handoff had closed the
-- request. A cancellation now writes its notice in the same transaction, and the same delivery hands it to the
-- agent. The column keeps its name: the customer's button is the customer's decision.
ALTER TABLE agent_notices DROP CONSTRAINT agent_notices_decision_check;
ALTER TABLE agent_notices ADD CONSTRAINT agent_notices_decision_check
    CHECK (decision IN ('approved', 'rejected', 'cancelled'));
