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
from refund_agent.agent.graph import Agent
from refund_agent.agent.model import ScriptedModel
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

    def server(self):
        """The agent of a newly started server, and its scripted model."""
        connection = database.checkpoint_connection("app", self.app.url.database)
        self.connections.append(connection)
        model = ScriptedModel(ANA_MUG)
        return Agent(self.app, POLICY, model, PostgresSaver(connection), lambda: NOW), model

    def asked_and_approved(self, agent):
        """Ana asks, the agent proposes, Ana confirms with her button and Rui approves: the notice is now stored."""
        agent.receive(self.conversation, "Please refund my blue mug.")
        proposal = rows(self.app, "SELECT id FROM proposals")[0][0]
        confirm(self.app, CUSTOMER, proposal, "confirmed", NOW, POLICY)
        assert decide(self.app, STAFF, proposal, "approved", NOW, POLICY) == "approved"
        return proposal


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
        decide(shop.app, STAFF, proposal, "rejected", NOW, POLICY)  # already decided
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
