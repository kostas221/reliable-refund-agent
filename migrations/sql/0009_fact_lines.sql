-- Which messages are fact lines (review of 2026-10-28). A fact line is said by the graph from the records, right after
-- the agent's answer (refund_agent/agent/facts.py), and was stored as an agent message like any other. The checks that
-- pair the customer's answer with the agent's message just before it (a yes to the offer of a person, a yes to a
-- question that named an item) then read the fact line instead of the offer or the question: in D40 try 2 of
-- 2026-10-27 a genuine yes was refused. The customer still sees the line as the agent's; the checks skip it.
ALTER TABLE messages ADD COLUMN fact_line boolean NOT NULL DEFAULT false;
