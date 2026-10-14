"""The chat door on a real PostgreSQL, with the scripted model: the customer talks to the agent over HTTP, and a staff
decision wakes the agent after its answer is sent.
"""

from types import SimpleNamespace

import pytest
from langgraph.checkpoint.postgres import PostgresSaver

from refund_agent import db as database
from refund_agent.agent.graph import Agent
from refund_agent.agent.model import Call, Say, ScriptedModel
from refund_agent.api.app import create_app
from refund_agent.api.auth import set_password
from refund_agent.fixtures import seed
from refund_agent.refunds import Actor, open_conversation
from tests.acceptance.flows import DEVELOPMENT, POLICY, rows
from tests.acceptance.test_http import PASSWORD, Browser, Clock
from tests.acceptance.test_scripted_agent import ANA_MUG


@pytest.fixture
def shop(db):
    connections = []

    def make(scenario_id="D01", script=ANA_MUG, with_agent=True):
        scenario = DEVELOPMENT[scenario_id]
        owner = db("owner")
        seed(owner, scenario, POLICY)
        people = {p.id: p.email for p in (*scenario.fixture.customers, *scenario.fixture.staff)}
        for person in people:
            set_password(owner, person, PASSWORD)
        engine = db("app")
        clock = Clock(scenario.now)
        model = ScriptedModel(script)
        agent = None
        if with_agent:
            connections.append(database.checkpoint_connection("app", engine.url.database))
            agent = Agent(engine, POLICY, model, PostgresSaver(connections[-1]), clock)
        api = create_app(engine, POLICY, clock, wall_clock=Clock(scenario.now), agent=agent)

        def browser(user_id):
            signed_in = Browser(api)
            assert signed_in.sign_in(people[user_id]).status_code == 200
            return signed_in

        return SimpleNamespace(scenario=scenario, engine=engine, model=model, agent=agent, browser=browser)

    yield make
    for connection in connections:
        connection.close()


def said(shop, conversation):
    return [(m["author"], m["content_untrusted"]) for m in conversation_of(shop, conversation)["messages"]]


def conversation_of(shop, conversation):
    return shop.browser(shop.scenario.customer.id).get(f"/api/conversations/{conversation}").json()


def test_the_customer_talks_to_the_agent_and_an_approval_wakes_it(shop):
    s = shop()
    ana, rui = s.browser("d01-ana"), s.browser("d01-rui")
    conversation = ana.post("/api/conversations").json()["conversation_id"]
    answer = ana.post(f"/api/conversations/{conversation}/messages", {"text": s.scenario.customer.opening_message})
    assert answer.json() == {
        "answers": ["I can refund R$ 49,90 for the blue mug. Please confirm on the proposal card."]
    }
    card = conversation_of(s, conversation)["proposals"][0]
    assert (card["status"], card["amount_minor"]) == ("awaiting_customer_confirmation", 4990)

    ana.post(f"/api/proposals/{card['proposal_id']}/confirmation", {"decision": "confirmed"})
    decision = rui.post(f"/api/staff/proposals/{card['proposal_id']}/decision", {"decision": "approved"})
    assert decision.json()["status"] == "approved"  # the staff answer; the agent is woken after it

    after = conversation_of(s, conversation)
    receipt = after["proposals"][0]["receipt"]["receipt_number"]
    assert after["proposals"][0]["status"] == "refunded"
    assert said(s, conversation)[-1] == ("agent", f"Your refund of R$ 49,90 is done: receipt {receipt}.")
    assert rows(s.engine, "SELECT count(*) FROM refund_operations") == [(1,)]


def test_a_rejection_wakes_the_agent_too(shop):
    script = [
        Call("propose_refund", {"order_id": "d04-o1", "unit_ids": ["d04-o1-u1"]}),
        Say("I can refund {propose_refund.amount_minor|brl} for the earbuds. Please confirm on the proposal card."),
        Say("A staff member reviewed the request and rejected it, so no refund will be made."),
    ]
    s = shop("D04", script)
    davi, rui = s.browser("d04-davi"), s.browser("d04-rui")
    conversation = davi.post("/api/conversations").json()["conversation_id"]
    davi.post(f"/api/conversations/{conversation}/messages", {"text": s.scenario.customer.opening_message})
    proposal = conversation_of(s, conversation)["proposals"][0]["proposal_id"]
    davi.post(f"/api/proposals/{proposal}/confirmation", {"decision": "confirmed"})
    rui.post(f"/api/staff/proposals/{proposal}/decision", {"decision": "rejected"})
    assert said(s, conversation)[-1] == (
        "agent",
        "A staff member reviewed the request and rejected it, so no refund will be made.",
    )
    assert rows(s.engine, "SELECT count(*) FROM refund_operations") == [(0,)]


def test_only_the_conversations_customer_can_talk_to_its_agent(shop):
    s = shop("D07")
    gabi, rui = s.browser("d07-gabi"), s.browser("d07-rui")
    hugos = open_conversation(s.engine, Actor("customer", "d07-hugo"), s.scenario.now)
    mine = gabi.post("/api/conversations").json()["conversation_id"]
    assert gabi.post(f"/api/conversations/{hugos}/messages", {"text": "Refund it."}).status_code == 404
    assert rui.post(f"/api/conversations/{mine}/messages", {"text": "Refund it."}).status_code == 403
    no_token = gabi.http.post(f"/api/conversations/{mine}/messages", json={"text": "Hi"})
    assert no_token.status_code == 403
    for body in (
        {"text": ""},
        {"text": "x" * 2001},
        {"text": "Hi", "configuration": "C"},
        {"text": "Hi", "actor": "agent"},
    ):
        assert gabi.post(f"/api/conversations/{mine}/messages", body).status_code == 422
    assert s.model.requests == []  # the model was never asked


def test_a_second_message_while_the_agent_answers_waits_its_turn(shop):
    s = shop()
    ana = s.browser("d01-ana")
    conversation = ana.post("/api/conversations").json()["conversation_id"]
    with s.agent._turn(conversation, wait=False):  # the agent is busy with an earlier message
        answer = ana.post(f"/api/conversations/{conversation}/messages", {"text": "Hello?"})
    assert (answer.status_code, answer.json()["detail"]) == (409, "the agent is still answering the previous message")


def test_after_a_handoff_the_chat_door_records_without_answering(shop):
    s = shop()
    ana = s.browser("d01-ana")
    conversation = ana.post("/api/conversations").json()["conversation_id"]
    ana.post(f"/api/conversations/{conversation}/handoff")
    answer = ana.post(f"/api/conversations/{conversation}/messages", {"text": "Is anyone there?"})
    assert answer.json() == {"answers": []}
    assert said(s, conversation) == [("customer", "Is anyone there?")]
    assert s.model.requests == []


def test_a_model_failure_is_a_503_and_the_message_is_kept(shop):
    s = shop(script=[])  # a model that cannot answer
    ana = s.browser("d01-ana")
    conversation = ana.post("/api/conversations").json()["conversation_id"]
    answer = ana.post(f"/api/conversations/{conversation}/messages", {"text": "Can I get a refund?"})
    assert (answer.status_code, answer.json()["detail"]) == (503, "the agent could not answer; please try again")
    assert said(s, conversation) == [("customer", "Can I get a refund?")]


def test_without_an_agent_the_chat_door_says_so(shop):
    s = shop(with_agent=False)
    ana = s.browser("d01-ana")
    conversation = ana.post("/api/conversations").json()["conversation_id"]
    assert ana.post(f"/api/conversations/{conversation}/messages", {"text": "Hi"}).status_code == 503
