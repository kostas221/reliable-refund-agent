"""First milestone of phase 2 (plan section 17): one correct refund transaction, without any LLM.

Scenario D01 on a real PostgreSQL, as the application role. Every expected value is written by hand here; this file
must not read the state machine or the policy functions to work out what should happen.
"""

from datetime import timedelta

import pytest
from sqlalchemy import text

from refund_agent.fixtures import seed
from refund_agent.policy import load_policy
from refund_agent.refunds import Actor, Refused, confirm, decide, execute, open_conversation, propose
from refund_agent.scenarios import load_split
from tests.acceptance.flows import home

POLICY = load_policy()
D01 = next(s for s in load_split("development") if s.id == "D01")
CUSTOMER = Actor("customer", "d01-ana")
AGENT = Actor("agent", "d01-ana")
STAFF = Actor("staff", "d01-rui")


def minutes(n: int):
    return D01.now + timedelta(minutes=n)


def rows(engine, sql):
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(text(sql))]


def test_one_refund_is_committed_once_and_every_retry_returns_the_same_receipt(db):
    seed(db("owner"), D01, POLICY)
    app = db("app")

    conversation = open_conversation(app, CUSTOMER, minutes(0))
    proposal = propose(app, AGENT, conversation, "d01-o1", ["d01-o1-u1"], "propose-1", minutes(1), POLICY)
    assert (proposal.status, proposal.amount_minor) == ("awaiting_customer_confirmation", 4990)

    # Before anyone agreed, the backend refuses and writes nothing.
    with pytest.raises(Refused) as refused:
        execute(app, AGENT, proposal.id, "execute-early", minutes(2), POLICY, conversation_id=home(app, proposal.id))
    assert refused.value.check == "status_approved"
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(0,)]

    assert confirm(app, CUSTOMER, proposal.id, "confirmed", minutes(3), POLICY) == "awaiting_staff_approval"
    assert decide(app, STAFF, proposal.id, "approved", minutes(4), POLICY) == "approved"

    receipt = execute(app, AGENT, proposal.id, "execute-1", minutes(5), POLICY, conversation_id=home(app, proposal.id))
    assert (receipt["amount_minor"], receipt["currency"], receipt["units"]) == (
        4990,
        "BRL",
        [{"unit_id": "d01-o1-u1", "amount_minor": 4990}],
    )
    # The HTTP answer was lost and the call is repeated, first with the same key, then with a new one.
    assert (
        execute(app, AGENT, proposal.id, "execute-1", minutes(6), POLICY, conversation_id=home(app, proposal.id))
        == receipt
    )
    assert (
        execute(app, AGENT, proposal.id, "execute-2", minutes(7), POLICY, conversation_id=home(app, proposal.id))
        == receipt
    )

    assert rows(app, "SELECT status FROM proposals") == [("refunded",)]
    assert rows(app, "SELECT count(*), sum(amount_minor) FROM refund_operations") == [(1, 4990)]
    assert rows(app, "SELECT order_unit_id, amount_minor FROM ledger_lines") == [("d01-o1-u1", 4990)]
    assert rows(app, "SELECT event, outcome, reason FROM audit_events ORDER BY id") == [
        ("open_conversation", "committed", None),
        ("propose", "committed", None),
        ("execute", "rejected", "status_approved"),
        ("confirm", "committed", None),
        ("decide", "committed", None),
        ("execute", "committed", None),
    ]


def test_the_receipt_survives_expiry(db):
    """A refund committed before a crash is still returned after the proposal's 72 hours have passed."""
    seed(db("owner"), D01, POLICY)
    app = db("app")
    conversation = open_conversation(app, CUSTOMER, minutes(0))
    proposal = propose(app, AGENT, conversation, "d01-o1", ["d01-o1-u1"], "propose-1", minutes(1), POLICY)
    confirm(app, CUSTOMER, proposal.id, "confirmed", minutes(2), POLICY)
    decide(app, STAFF, proposal.id, "approved", minutes(3), POLICY)
    receipt = execute(app, AGENT, proposal.id, "execute-1", minutes(4), POLICY, conversation_id=home(app, proposal.id))

    four_days_later = minutes(4 * 24 * 60)
    assert (
        execute(app, AGENT, proposal.id, "execute-1", four_days_later, POLICY, conversation_id=home(app, proposal.id))
        == receipt
    )
    assert rows(app, "SELECT count(*) FROM ledger_lines") == [(1,)]


def test_an_approval_after_expiry_is_refused_and_the_proposal_is_closed(db):
    seed(db("owner"), D01, POLICY)
    app = db("app")
    conversation = open_conversation(app, CUSTOMER, minutes(0))
    proposal = propose(app, AGENT, conversation, "d01-o1", ["d01-o1-u1"], "propose-1", minutes(0), POLICY)
    confirm(app, CUSTOMER, proposal.id, "confirmed", minutes(1), POLICY)

    # 72 hours after creation the proposal can no longer be approved.
    with pytest.raises(Refused) as refused:
        decide(app, STAFF, proposal.id, "approved", minutes(72 * 60), POLICY)
    assert refused.value.check == "proposal_current"
    assert rows(app, "SELECT status, status_reason FROM proposals") == [("expired", "expired")]
    assert rows(app, "SELECT count(*) FROM staff_decisions") == [(0,)]
