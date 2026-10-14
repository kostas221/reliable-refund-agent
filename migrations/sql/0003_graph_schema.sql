-- The conversation graph's checkpoints (plan section 5): memory for resuming a conversation, never authority.
-- LangGraph's PostgresSaver creates its own tables in this schema (refund_agent.db.migrate runs its setup as
-- refund_owner). The application role may read and write them; the domain services never read this schema.
CREATE SCHEMA graph AUTHORIZATION refund_owner;
GRANT USAGE ON SCHEMA graph TO refund_app;
ALTER DEFAULT PRIVILEGES FOR ROLE refund_owner IN SCHEMA graph
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO refund_app;
