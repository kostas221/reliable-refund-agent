-- What the live model cost, one row per attempt (closing plan, live mode; outside critique of 2026-11-01). The live
-- server holds one budget for every call of the agent's model, those a customer's message starts and those a staff
-- decision starts from the background, and writes each settled attempt here. A server started again on the same
-- database (--keep) adds these rows up and goes on from there, so a restart never resets what was spent. A row is
-- never changed or removed: the runtime role may only add and read.
CREATE TABLE model_spend (
    id text PRIMARY KEY,
    at timestamptz NOT NULL,
    role text NOT NULL CHECK (role IN ('agent', 'simulator')),
    usd numeric(12, 8) NOT NULL CHECK (usd >= 0),
    uncertain boolean NOT NULL
);

GRANT SELECT, INSERT ON model_spend TO refund_app;
