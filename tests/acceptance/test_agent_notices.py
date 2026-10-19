"""Notices to the agent survive a stopped server (outside review of 2026-10-15; plan section 2, item 8).

A staff decision stores its notice in the same transaction. deliver_pending() hands the stored notices to the agent
and marks each delivered after the agent's run; a notice the agent already applied changes nothing when it comes
again. Each agent below is built like a newly started server: its own checkpoint connection, nothing in memory.
Expected values are written by hand.
"""

import time

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres import PostgresSaver

from refund_agent import db as database
from refund_agent import reads
from refund_agent.agent.graph import Agent
from refund_agent.agent.model import ModelError, ScriptedModel
from refund_agent.agent.notices import MAX_ATTEMPTS, deliver_pending
from refund_agent.api.app import create_app
from refund_agent.fixtures import seed
from refund_agent.refunds import Actor, Refused, confirm, decide, hand_off, open_conversation
from tests.acceptance.flows import DEVELOPMENT, POLICY, rows
from tests.acceptance.test_scripted_agent import ANA_MUG

D01 = DEVELOPMENT["D01"]
NOW = D01.now
CUSTOMER, STAFF = Actor("customer", "d01-ana"), Actor("staff", "d01-rui")
NOTICES = "SELECT decision, attempts, delivered_at IS NOT NULL, last_error IS NOT NULL FROM agent_notices"


class Shop:
    def __init__(self, db):
        seed(db("owner"), D01, POLICY)
        self.db, self.app = db, db("app")
        self.connections = []
        self.conversation = open_conversation(self.app, CUSTOMER, NOW)

    def server(self, model=None):
        """The agent of a newly started server, and its scripted model."""
        connection = database.checkpoint_connection("app", self.app.url.database)
        self.connections.append(connection)
        model = model or ScriptedModel(ANA_MUG)
        return Agent(self.app, POLICY, model, PostgresSaver(connection), lambda: NOW), model

    def asked_and_approved(self, agent):
        """Ana asks, the agent proposes, Ana confirms with her button and Rui approves: the notice is now stored."""
        agent.receive(self.conversation, "Please refund my blue mug.")
        proposal = rows(self.app, "SELECT id FROM proposals")[0][0]
        confirm(self.app, CUSTOMER, proposal, "confirmed", NOW, POLICY)
        assert decide(self.app, STAFF, proposal, "approved", NOW, POLICY) == "approved"
        return proposal


class FailsOnce(ScriptedModel):
    """The scripted model, failing once where it would say line `at` (0-based) of ANA_MUG, then working."""

    def __init__(self, at: int) -> None:
        super().__init__(ANA_MUG)
        self.at, self.failed = at, False

    def respond(self, instructions, messages, tools):
        if not self.failed and sum(1 for m in messages if m["role"] == "agent") == self.at:
            self.failed = True
            raise ModelError("server", retryable=False, detail="the provider is down for a moment")
        return super().respond(instructions, messages, tools)


@pytest.fixture
def shop(db):
    made = Shop(db)
    yield made
    for connection in made.connections:
        connection.close()


def test_a_decision_stores_its_notice_with_it_and_a_refused_one_stores_none(shop):
    agent, _ = shop.server()
    proposal = shop.asked_and_approved(agent)
    assert rows(shop.app, NOTICES) == [("approved", 0, False, False)]
    assert rows(shop.app, "SELECT conversation_id, proposal_id FROM agent_notices") == [(shop.conversation, proposal)]
    with pytest.raises(Refused):
        decide(shop.app, STAFF, proposal, "rejected", NOW, POLICY, reason="Damaged.")  # already decided
    assert rows(shop.app, "SELECT count(*) FROM agent_notices") == [(1,)]


def test_a_notice_stored_before_the_server_stopped_is_delivered_after_it_starts_again(shop):
    first, _ = shop.server()
    shop.asked_and_approved(first)  # ... and the server stops before it tells the agent
    assert rows(shop.app, "SELECT count(*) FROM refund_operations") == [(0,)]

    restarted, _ = shop.server()
    assert deliver_pending(shop.app, restarted, lambda: NOW) == 1
    assert rows(shop.app, "SELECT count(*) FROM refund_operations") == [(1,)]
    assert rows(shop.app, NOTICES) == [("approved", 1, True, False)]
    assert restarted.messages(shop.conversation)[-1]["text"] == "Your refund of R$ 49,90 is done: receipt R-00000001."


def test_a_notice_delivered_twice_is_applied_once(shop):
    agent, _ = shop.server()
    shop.asked_and_approved(agent)
    assert deliver_pending(shop.app, agent, lambda: NOW) == 1
    said = len(agent.messages(shop.conversation))
    # A crash after the agent's run and before the delivery was marked: the notice reads as pending again.
    with shop.db("owner").begin() as conn:
        conn.exec_driver_sql("UPDATE agent_notices SET delivered_at = NULL, attempts = 0")

    restarted, model = shop.server()
    assert deliver_pending(shop.app, restarted, lambda: NOW) == 1  # marked delivered ...
    assert model.requests == []  # ... without asking the model again
    assert len(restarted.messages(shop.conversation)) == said
    assert rows(shop.app, "SELECT count(*) FROM refund_operations") == [(1,)]
    assert rows(shop.app, "SELECT count(*) FROM messages WHERE content_untrusted LIKE 'Your refund%'") == [(1,)]


def untold(shop):
    """What the staff queue lists as decisions the agent has not been told of."""
    with shop.app.connect() as conn:
        return [(n["decision"], n["attempts"]) for n in reads.staff_queue(conn, NOW, POLICY)["untold_decisions"]]


@pytest.mark.parametrize(
    ("fails_at", "paid_before_the_failure"),
    [
        (4, 0),  # on the approval notice itself, before it pays (line 5: execute_refund)
        (5, 1),  # after the refund committed, before the agent tells the customer (line 6)
    ],
)
def test_a_notice_whose_run_failed_is_finished_by_the_next_delivery(shop, fails_at, paid_before_the_failure):
    # Review of 2026-10-19, R1: the notice was recorded in the conversation before the model failed, and the next
    # delivery found it there and was marked delivered with nothing paid. Now it finishes the run first.
    agent, _ = shop.server(FailsOnce(fails_at))
    shop.asked_and_approved(agent)
    assert deliver_pending(shop.app, agent, lambda: NOW) == 0  # the model failed; tried again later
    assert rows(shop.app, NOTICES) == [("approved", 1, False, True)]
    assert rows(shop.app, "SELECT count(*) FROM refund_operations") == [(paid_before_the_failure,)]
    assert untold(shop) == [("approved", 1)]  # the staff member sees that the agent was not told

    restarted, _ = shop.server()  # the server's next round of deliveries, the model working again
    assert deliver_pending(shop.app, restarted, lambda: NOW) == 1
    assert rows(shop.app, "SELECT count(*) FROM refund_operations") == [(1,)]  # paid, and once
    assert rows(shop.app, NOTICES) == [("approved", 2, True, False)]
    assert restarted.messages(shop.conversation)[-1]["text"] == "Your refund of R$ 49,90 is done: receipt R-00000001."
    assert untold(shop) == []


def test_no_notice_wakes_a_conversation_a_person_took_over(shop):
    agent, _ = shop.server()
    shop.asked_and_approved(agent)
    hand_off(shop.app, CUSTOMER, shop.conversation, "the customer asked for a person", NOW)

    restarted, model = shop.server()
    assert deliver_pending(shop.app, restarted, lambda: NOW) == 1
    assert model.requests == []
    assert rows(shop.app, "SELECT count(*) FROM refund_operations") == [(0,)]
    assert rows(shop.app, NOTICES) == [("approved", 1, True, False)]


def test_a_delivery_that_keeps_failing_stops_after_three_attempts(shop):
    agent, _ = shop.server()
    shop.asked_and_approved(agent)

    class Broken:
        calls = 0

        def notify(self, *args, **kwargs):
            Broken.calls += 1
            raise RuntimeError("the model is down")

    for _ in range(MAX_ATTEMPTS + 1):
        assert deliver_pending(shop.app, Broken(), lambda: NOW) == 0
    assert Broken.calls == MAX_ATTEMPTS == 3
    assert rows(shop.app, NOTICES) == [("approved", 3, False, True)]
    assert rows(shop.app, "SELECT count(*) FROM refund_operations") == [(0,)]
    assert untold(shop) == [("approved", 3)]  # no more attempts: the staff member is shown it


def test_the_server_delivers_pending_notices_when_it_starts(shop):
    first, _ = shop.server()
    shop.asked_and_approved(first)  # stored, never delivered

    restarted, _ = shop.server()
    app = create_app(shop.app, POLICY, lambda: NOW, agent=restarted, deliver_every_s=0.2)
    with TestClient(app, base_url="https://testserver"):  # the server starts: its delivery loop runs
        for _ in range(100):  # the notice is marked last, after the agent's whole run
            if rows(shop.app, "SELECT count(*) FROM agent_notices WHERE delivered_at IS NOT NULL") == [(1,)]:
                break
            time.sleep(0.1)
    assert rows(shop.app, "SELECT count(*) FROM refund_operations") == [(1,)]
    assert rows(shop.app, NOTICES) == [("approved", 1, True, False)]
