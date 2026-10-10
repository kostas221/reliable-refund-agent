"""Shared steps for the acceptance tests. They drive the services; expected values stay in the tests, by hand."""

from datetime import datetime

from sqlalchemy import text

from refund_agent.policy import load_policy
from refund_agent.refunds import Actor, Refused, confirm, decide, execute, open_conversation, propose
from refund_agent.scenarios import load_split

POLICY = load_policy()
DEVELOPMENT = {s.id: s for s in load_split("development")}


def proposed(app, customer: str, order: str, units: list[str], key: str, now: datetime, conversation=None):
    """A proposal by the agent in `conversation`, or in a new conversation of `customer`."""
    conversation = conversation or open_conversation(app, Actor("customer", customer), now)
    return conversation, propose(app, Actor("agent", customer), conversation, order, units, key, now, POLICY)


def approved(app, customer: str, staff: str, order: str, units: list[str], key: str, now: datetime) -> str:
    """A proposal in a new conversation of `customer`, confirmed and approved; returns its ID."""
    _, proposal = proposed(app, customer, order, units, key, now)
    confirm(app, Actor("customer", customer), proposal.id, "confirmed", now, POLICY)
    decide(app, Actor("staff", staff), proposal.id, "approved", now, POLICY)
    return proposal.id


def attempt(app, customer: str, proposal_id: str, key: str, now: datetime):
    """Execute as the customer's agent; ("receipt", receipt) or ("refused", check)."""
    try:
        return "receipt", execute(app, Actor("agent", customer), proposal_id, key, now, POLICY)
    except Refused as refused:
        return "refused", refused.check


def refused_check(call) -> str:
    try:
        call()
    except Refused as refused:
        return refused.check
    raise AssertionError("the call was not refused")


def rows(app, sql: str) -> list[tuple]:
    with app.connect() as conn:
        return [tuple(row) for row in conn.execute(text(sql))]
