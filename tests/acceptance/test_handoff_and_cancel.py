"""Cancellation by the customer and handoff to a person, on a real PostgreSQL (acceptance 3; failure case 11).

Expected values are written by hand.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from refund_agent import refunds
from refund_agent.fixtures import seed
from refund_agent.refunds import (
    Actor,
    cancel,
    confirm,
    decide,
    execute,
    hand_off,
    open_conversation,
    propose,
    take_handoff,
)
from tests.acceptance.flows import (
    DEVELOPMENT,
    POLICY,
    approved,
    attempt,
    hold_at,
    home,
    proposed,
    refused_check,
    rows,
)

D01 = DEVELOPMENT["D01"]
NOW = D01.now
CUSTOMER, AGENT, STAFF = Actor("customer", "d01-ana"), Actor("agent", "d01-ana"), Actor("staff", "d01-rui")


@pytest.fixture
def app(db):
    seed(db("owner"), D01, POLICY)
    return db("app")


# Cancellation


def test_cancel_after_confirming_ends_the_proposal_for_good(app):
    _, proposal = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    confirm(app, CUSTOMER, proposal.id, "confirmed", NOW, POLICY)

    assert cancel(app, CUSTOMER, proposal.id, NOW, POLICY) == "cancelled"
    assert refused_check(lambda: decide(app, STAFF, proposal.id, "approved", NOW, POLICY)) == "invalid_transition"
    assert (
        refused_check(
            lambda: execute(app, AGENT, proposal.id, "execute-1", NOW, POLICY, conversation_id=home(app, proposal.id))
        )
        == "status_approved"
    )
    assert rows(app, "SELECT status, status_reason FROM proposals") == [("cancelled", "cancelled_by_customer")]
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(0,)]


def test_cancel_after_approval_still_stops_the_refund(app):
    proposal_id = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    assert cancel(app, CUSTOMER, proposal_id, NOW, POLICY) == "cancelled"
    assert attempt(app, "d01-ana", proposal_id, "execute-1", NOW) == ("refused", "status_approved")


def test_a_refunded_proposal_cannot_be_cancelled(app):
    proposal_id = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    execute(app, AGENT, proposal_id, "execute-1", NOW, POLICY, conversation_id=home(app, proposal_id))
    assert refused_check(lambda: cancel(app, CUSTOMER, proposal_id, NOW, POLICY)) == "invalid_transition"
    assert rows(app, "SELECT status FROM proposals") == [("refunded",)]


@pytest.mark.parametrize("actor", [AGENT, STAFF])
def test_only_the_customer_cancels(app, actor):
    _, proposal = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    assert refused_check(lambda: cancel(app, actor, proposal.id, NOW, POLICY)) == "actor_owns"
    assert rows(app, "SELECT status FROM proposals") == [("awaiting_customer_confirmation",)]


def test_cancelling_an_expired_proposal_records_that_it_expired(app):
    _, proposal = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    assert cancel(app, CUSTOMER, proposal.id, NOW + timedelta(hours=72), POLICY) == "expired"
    assert rows(app, "SELECT status, status_reason FROM proposals") == [("expired", "expired")]


# Handoff


def test_handoff_stops_the_agent_and_withdraws_the_open_proposal(app):
    conversation, proposal = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    handoff_id = hand_off(
        app,
        AGENT,
        conversation,
        "customer_request",
        NOW,
        origin="customer",
        customer_goal_untrusted="Refund for the mug",
    )

    assert rows(app, "SELECT control FROM conversations") == [("human_controlled",)]
    assert rows(app, "SELECT status, status_reason FROM proposals") == [("invalidated", "handed_off")]
    origin, status, pending, prior = rows(
        app, "SELECT origin, status, pending_proposal_id, prior_actions FROM handoffs"
    )[0]
    assert (origin, status, pending) == ("customer", "open", proposal.id)
    assert [action["event"] for action in prior] == ["open_conversation", "propose"]
    # The audit keeps the agent as the actor, whatever origin it reported.
    assert rows(app, "SELECT actor_type, details->>'origin' FROM audit_events WHERE event = 'hand_off'") == [
        ("agent", "customer")
    ]

    # From now on the agent changes nothing, and the old proposal cannot be confirmed.
    later = NOW + timedelta(minutes=1)
    assert (
        refused_check(lambda: propose(app, AGENT, conversation, "d01-o1", ["d01-o1-u1"], "propose-2", later, POLICY))
        == "agent_in_control"
    )
    assert refused_check(lambda: confirm(app, CUSTOMER, proposal.id, "confirmed", later, POLICY)) == (
        "invalid_transition"
    )
    assert rows(app, "SELECT count(*) FROM proposals") == [(1,)]
    assert handoff_id == rows(app, "SELECT id FROM handoffs")[0][0]


def test_a_second_handoff_request_returns_the_first(app):
    conversation, _ = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    first = hand_off(app, AGENT, conversation, "policy:window", NOW)
    assert hand_off(app, CUSTOMER, conversation, "customer_request", NOW) == first
    assert rows(app, "SELECT count(*) FROM handoffs") == [(1,)]


def test_a_staff_takeover_is_recorded_as_taken_by_that_staff_member(app):
    conversation, _ = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    hand_off(app, STAFF, conversation, "staff_review", NOW)
    assert rows(app, "SELECT origin, status, taken_by FROM handoffs") == [("staff", "taken", "d01-rui")]


def test_staff_take_an_open_handoff_once(app):
    conversation, _ = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    handoff_id = hand_off(app, AGENT, conversation, "policy:window", NOW)
    assert refused_check(lambda: take_handoff(app, CUSTOMER, handoff_id, NOW)) == "staff_role"
    take_handoff(app, STAFF, handoff_id, NOW)
    assert refused_check(lambda: take_handoff(app, STAFF, handoff_id, NOW)) == "invalid_transition"
    assert rows(app, "SELECT status, taken_by FROM handoffs") == [("taken", "d01-rui")]


def test_nobody_hands_off_another_customers_conversation(db):
    seed(db("owner"), DEVELOPMENT["D07"], POLICY)
    app = db("app")
    conversation, _ = proposed(app, "d07-hugo", "d07-o2", ["d07-o2-u1"], "propose-1", NOW)
    foreign = Actor("agent", "d07-gabi")
    assert refused_check(lambda: hand_off(app, foreign, conversation, "customer_request", NOW)) == "actor_owns"
    assert rows(app, "SELECT control FROM conversations") == [("agent",)]


# Handoff and execution at the same time (acceptance 3, failure case 11)


def test_refund_first_then_handoff_the_refund_stays(app, monkeypatch):
    proposal_id = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    conversation = rows(app, "SELECT conversation_id FROM proposals")[0][0]
    inside, release = threading.Event(), threading.Event()
    monkeypatch.setattr(refunds, "failpoint", hold_at("execute", inside, release))

    with ThreadPoolExecutor(2) as pool:
        refund = pool.submit(attempt, app, "d01-ana", proposal_id, "execute-1", NOW)
        assert inside.wait(10)
        handoff = pool.submit(hand_off, app, CUSTOMER, conversation, "customer_request", NOW)
        time.sleep(0.5)
        assert not handoff.done()  # waiting for the conversation lock held by the refund
        release.set()
        kind, _ = refund.result(10)
        handoff.result(10)

    assert kind == "receipt"
    assert rows(app, "SELECT status FROM proposals") == [("refunded",)]
    assert rows(app, "SELECT pending_proposal_id FROM handoffs") == [(None,)]
    assert rows(app, "SELECT count(*) FROM ledger_lines") == [(1,)]


def test_handoff_first_then_refund_nothing_is_paid(app, monkeypatch):
    proposal_id = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    conversation = rows(app, "SELECT conversation_id FROM proposals")[0][0]
    inside, release = threading.Event(), threading.Event()
    monkeypatch.setattr(refunds, "failpoint", hold_at("hand_off", inside, release))

    with ThreadPoolExecutor(2) as pool:
        handoff = pool.submit(hand_off, app, CUSTOMER, conversation, "customer_request", NOW)
        assert inside.wait(10)
        refund = pool.submit(attempt, app, "d01-ana", proposal_id, "execute-1", NOW)
        time.sleep(0.5)
        assert not refund.done()  # waiting for the conversation lock held by the handoff
        release.set()
        handoff.result(10)
        outcome = refund.result(10)

    assert outcome == ("refused", "agent_in_control")
    assert rows(app, "SELECT status, status_reason FROM proposals") == [("invalidated", "handed_off")]
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(0,)]
    assert rows(app, "SELECT pending_proposal_id FROM handoffs") == [(proposal_id,)]


# The agent pays only from the conversation the request was made in (review of 2026-10-15)


def test_an_agent_pays_only_the_requests_of_its_own_conversation(app):
    proposal_id = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)  # conversation A
    other = open_conversation(app, CUSTOMER, NOW)  # conversation B, the same customer
    assert attempt(app, "d01-ana", proposal_id, "execute-1", NOW, conversation=other) == (
        "refused",
        "same_conversation",
    )
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(0,)]
    assert rows(app, "SELECT event, reason FROM audit_events WHERE outcome = 'rejected'") == [
        ("execute", "same_conversation")
    ]
    # The approval is untouched: the agent of the conversation it was made in can still pay it.
    assert attempt(app, "d01-ana", proposal_id, "execute-2", NOW)[0] == "receipt"
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(1,)]


def test_a_handoff_stops_a_call_from_that_conversation_for_a_request_made_elsewhere(app, monkeypatch):
    # Conversation B is being handed to a person while its agent, already on its way, asks to pay a request approved
    # in conversation A. Before this check, only A's control was read under A's lock, so the payment went through.
    proposal_id = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    other = open_conversation(app, CUSTOMER, NOW)
    inside, release = threading.Event(), threading.Event()
    monkeypatch.setattr(refunds, "failpoint", hold_at("hand_off", inside, release))

    with ThreadPoolExecutor(2) as pool:
        handoff = pool.submit(hand_off, app, CUSTOMER, other, "customer_request", NOW)
        assert inside.wait(10)
        refund = pool.submit(attempt, app, "d01-ana", proposal_id, "execute-1", NOW, other)
        outcome = refund.result(10)  # refused at once, while B's handoff is still open
        release.set()
        handoff.result(10)

    assert outcome == ("refused", "same_conversation")
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(0,)]
    assert rows(app, f"SELECT control FROM conversations WHERE id = '{other}'") == [("human_controlled",)]
    assert rows(app, "SELECT status FROM proposals") == [("approved",)]  # A's request waits for A's agent
