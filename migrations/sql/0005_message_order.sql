-- One order for what was said and what was done (outside review of 2026-10-15). A message takes its place from the
-- audit log's own counter, so a message and the audit event of a proposal, a decision or a handoff compare exactly:
-- times alone could not, since the messages of one turn shared one time. The agent's messages are written as soon as
-- they are said, after each step of its run, not at the end of the turn.
ALTER TABLE messages ADD COLUMN seq bigint NOT NULL DEFAULT nextval('audit_events_id_seq'::regclass);
CREATE INDEX messages_conversation_order ON messages (conversation_id, seq);

-- The application takes the next number; it cannot set or reset the counter.
GRANT USAGE ON SEQUENCE audit_events_id_seq TO refund_app;
