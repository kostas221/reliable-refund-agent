"""The schema accepts every development fixture and refuses what the application role must never do."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from refund_agent.fixtures import seed
from refund_agent.policy import load_policy
from refund_agent.scenarios import load_split

POLICY = load_policy()
DEVELOPMENT = {s.id: s for s in load_split("development")}


@pytest.mark.parametrize("scenario_id", sorted(DEVELOPMENT))
def test_every_development_fixture_loads_under_all_constraints(db, scenario_id):
    seed(db("owner"), DEVELOPMENT[scenario_id], POLICY)
    with db("app").connect() as conn:
        units = conn.execute(text("SELECT count(*) FROM order_units")).scalar_one()
    assert units == sum(len(o.units) for o in DEVELOPMENT[scenario_id].fixture.orders)


@pytest.mark.parametrize(
    ("statement", "error"),
    [
        (
            "INSERT INTO orders (id, customer_id, status, purchased_at, source) "
            "VALUES ('x', 'd03-caio', 'delivered', now(), 'synthetic')",
            "permission denied",
        ),
        ("UPDATE order_units SET paid_minor = 1", "permission denied"),
        ("UPDATE proposals SET amount_minor = 1", "permission denied"),
        ("DELETE FROM proposals", "permission denied"),
        ("DELETE FROM proposal_units", "permission denied"),
        ("UPDATE refund_operations SET amount_minor = 1", "permission denied"),
        ("DELETE FROM ledger_lines", "permission denied"),
        ("UPDATE audit_events SET outcome = 'committed'", "permission denied"),
        ("DELETE FROM audit_events", "permission denied"),
        # Units cannot be added to a proposal created by another transaction (here, the loaded history).
        (
            "INSERT INTO proposal_units (proposal_id, order_unit_id, amount_minor) "
            "VALUES ('d03-r1', 'd03-o1-u3', 3324)",
            "only in the transaction that created the proposal",
        ),
        # The creating transaction is set by the database, never by the application.
        (
            "INSERT INTO proposals (id, request_key, request_hash, conversation_id, customer_id, order_id, "
            "amount_minor, currency, policy_version, policy_hash, order_material_version, status, created_at, "
            "expires_at, content_hash, created_xact) VALUES ('p', 'k', 'h', 'd03-caio-history', 'd03-caio', "
            "'d03-o1', 0, 'BRL', 'v1', 'h', 1, 'cancelled', now(), now(), 'h', pg_current_xact_id())",
            "permission denied",
        ),
        # Sign-in: the application checks passwords and records sessions, but cannot change who someone is.
        ("UPDATE users SET password_hash = 'x'", "permission denied"),
        ("UPDATE users SET role = 'staff'", "permission denied"),
        ("UPDATE sessions SET user_id = 'd03-rui'", "permission denied"),
        ("UPDATE sessions SET expires_at = now() + interval '1 year'", "permission denied"),
        ("DELETE FROM sessions", "permission denied"),
        # Notices to the agent: delivery is marked, but a notice cannot be removed or changed in what it says.
        ("DELETE FROM agent_notices", "permission denied"),
        ("UPDATE agent_notices SET decision = 'approved'", "permission denied"),
        ("UPDATE agent_notices SET proposal_id = 'd03-r1'", "permission denied"),
    ],
)
def test_application_role_is_refused(db, statement, error):
    seed(db("owner"), DEVELOPMENT["D03"], POLICY)
    with pytest.raises(DBAPIError, match=error), db("app").begin() as conn:
        conn.execute(text(statement))
