"""Shared steps for the acceptance tests. They drive the services; expected values stay in the tests, by hand."""

import threading
from datetime import datetime

from sqlalchemy import text

from refund_agent.policy import load_policy
from refund_agent.refunds import Actor, Refused, confirm, decide, execute, open_conversation, propose
from refund_agent.scenarios import load_split

POLICY = load_policy()
DEVELOPMENT = {s.id: s for s in load_split("development")}
# Held-out files are only checked here, before the freeze: they load, and the tools and the evaluator handle
# them. No agent or model runs them until the final evaluation (docs/scenarios.md).
SCENARIOS = {**DEVELOPMENT, **{s.id: s for s in load_split("held_out")}}


def proposed(app, customer: str, order: str, units: list[str], key: str, now: datetime, conversation=None):
    """A proposal by the agent in `conversation`, or in a new conversation of `customer`."""
    conversation = conversation or open_conversation(app, Actor("customer", customer), now)
    return conversation, propose(app, Actor("agent", customer), conversation, order, units, key, now, POLICY)


def home(app, proposal_id: str) -> str | None:
    """The conversation a proposal was made in. Its agent, and no other, may ask to pay it."""
    with app.connect() as conn:
        return conn.execute(text("SELECT conversation_id FROM proposals WHERE id = :id"), {"id": proposal_id}).scalar()


def approved(app, customer: str, staff: str, order: str, units: list[str], key: str, now: datetime) -> str:
    """A proposal in a new conversation of `customer`, confirmed and approved; returns its ID."""
    _, proposal = proposed(app, customer, order, units, key, now)
    confirm(app, Actor("customer", customer), proposal.id, "confirmed", now, POLICY)
    decide(app, Actor("staff", staff), proposal.id, "approved", now, POLICY)
    return proposal.id


def attempt(app, customer: str, proposal_id: str, key: str, now: datetime, conversation: str | None = None):
    """Execute as the customer's agent in `conversation`, by default the proposal's own; ("receipt", receipt) or
    ("refused", check)."""
    origin = conversation or home(app, proposal_id)
    try:
        return "receipt", execute(app, Actor("agent", customer), proposal_id, key, now, POLICY, conversation_id=origin)
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


def hold_at(point: str, inside: threading.Event, release: threading.Event):
    """A failpoint that keeps the transaction reaching `point` open until `release` is set."""

    def failpoint(reached: str, key: str) -> None:
        if reached == point:
            inside.set()
            assert release.wait(10)

    return failpoint
