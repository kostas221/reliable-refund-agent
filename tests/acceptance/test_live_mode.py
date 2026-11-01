"""The live-model mode on a real PostgreSQL (refund_agent/api/live.py), with a scripted model behind a budget in place
of the paid one: what was spent survives a restart, and a stop by the budget is a pause that loses nothing (outside
critique of the closing plan, 2026-11-01)."""

from types import SimpleNamespace

import pytest
from langgraph.checkpoint.postgres import PostgresSaver

from refund_agent import db as database
from refund_agent.agent import notices
from refund_agent.agent.costs import Budget
from refund_agent.agent.graph import Agent
from refund_agent.agent.model import Call, Say, ScriptedModel
from refund_agent.api import live
from refund_agent.api.app import create_app
from refund_agent.api.auth import set_password
from refund_agent.fixtures import seed
from tests.acceptance.flows import DEVELOPMENT, POLICY, rows
from tests.acceptance.test_http import PASSWORD, Browser, Clock

WORST, COST = 0.01, 0.002  # what each request holds first, and what it is then settled at

SCRIPT = [
    Call("propose_refund", {"order_id": "d01-o1", "unit_ids": ["d01-o1-u1"]}),
    Say("I can refund {propose_refund.amount_minor|brl} for the blue mug. Please confirm on the proposal card."),
    Say("A staff member is reviewing your request."),  # the answer to the message sent while paused
    Call("execute_refund"),
    Say("Your refund is done: receipt {execute_refund.receipt.receipt_number}."),
]


class Budgeted:
    """The scripted model behind a budget, as OpenAIResponses is: each request holds its worst case, then is settled."""

    name = "test-model/low"

    def __init__(self, budget, script=SCRIPT):
        self.inner, self.budget = ScriptedModel(script), budget

    def respond(self, instructions, messages, tools):
        self.budget.reserve(WORST)
        try:
            return self.inner.respond(instructions, messages, tools)
        finally:
            self.budget.settle("agent", COST, reserved=WORST)


@pytest.fixture
def server(db):
    """start(limit) starts the server on the shop's database, as `--live --keep` would: one budget with what the
    database recorded, a new agent and new doors; the database and the checkpoints are kept between starts."""
    scenario = DEVELOPMENT["D01"]
    owner = db("owner")
    seed(owner, scenario, POLICY)
    for person in (*scenario.fixture.customers, *scenario.fixture.staff):
        set_password(owner, person.id, PASSWORD)
    engine = db("app")
    clock = Clock(scenario.now)
    connection = database.checkpoint_connection("app", engine.url.database)

    def start(limit_usd, script=SCRIPT):
        budget = live.session_budget(engine, limit_usd)
        agent = Agent(engine, POLICY, Budgeted(budget, script), PostgresSaver(connection), clock)
        api = create_app(engine, POLICY, clock, wall_clock=Clock(scenario.now), agent=agent, budget=budget)

        def browser(user_id):
            signed_in = Browser(api)
            email = next(p.email for p in (*scenario.fixture.customers, *scenario.fixture.staff) if p.id == user_id)
            assert signed_in.sign_in(email).status_code == 200
            return signed_in

        return SimpleNamespace(budget=budget, agent=agent, api=api, browser=browser, engine=engine, clock=clock)

    yield start
    connection.close()


def test_what_was_spent_survives_a_restart_and_the_runtime_role_cannot_rewrite_it(server):
    first = server(1.0)
    first.budget.reserve(0.3)
    first.budget.settle("agent", 0.25, uncertain=True, reserved=0.3)
    first.budget.reserve(0.3)
    first.budget.settle("agent", 0.05, reserved=0.3)
    again = server(1.0)
    assert again.budget.spent_usd == pytest.approx(0.3)
    assert again.budget.uncertain_usd == pytest.approx(0.25)
    assert again.budget.by_role == {"agent": pytest.approx(0.3)}
    assert server(0.2).budget.left_usd == 0  # a smaller limit than what was spent: nothing more is sent


def test_a_paused_agent_loses_nothing_and_pays_once_after_the_owner_resumes(server):
    s = server(1.0)
    ana, rui = s.browser("d01-ana"), s.browser("d01-rui")
    conversation = ana.post("/api/conversations").json()["conversation_id"]
    ana.post(f"/api/conversations/{conversation}/messages", {"text": DEVELOPMENT["D01"].customer.opening_message})
    proposal = ana.get(f"/api/conversations/{conversation}").json()["proposals"][0]["proposal_id"]
    ana.post(f"/api/proposals/{proposal}/confirmation", {"decision": "confirmed"})

    s.budget.limit_usd = s.budget.spent_usd  # the budget runs out
    asked = ana.post(f"/api/conversations/{conversation}/messages", {"text": "Is it approved yet?"})
    assert (asked.status_code, asked.json()["detail"]) == (503, "agent_paused")
    stored = rows(s.engine, f"SELECT content_untrusted FROM messages WHERE conversation_id = '{conversation}'")
    assert stored[-1] == ("Is it approved yet?",)  # the customer's message is kept

    decided = rui.post(f"/api/staff/proposals/{proposal}/decision", {"decision": "approved"})
    assert decided.json()["status"] == "approved"  # the decision is stored; its delivery is paused
    assert rows(s.engine, "SELECT attempts, delivered_at FROM agent_notices") == [(0, None)]  # not a failed attempt
    assert rows(s.engine, "SELECT count(*) FROM refund_operations") == [(0,)]
    mode = ana.get("/api/mode").json()
    assert mode["agent"] == "model" and mode["model"] == "test-model/low" and mode["payments"] == "simulated"
    assert "over the limit" in mode["paused"] and mode["decisions_waiting"] == 1
    assert mode["budget"]["left_usd"] == 0

    resumed = server(1.0)  # the owner starts the server again on the same database, with more room
    assert resumed.budget.spent_usd == pytest.approx(s.budget.spent_usd)
    assert notices.deliver_pending(resumed.engine, resumed.agent, resumed.clock) == 1
    said = [m["text"] for m in resumed.agent.messages(conversation) if m["role"] == "agent" and m.get("text")]
    receipt = rows(resumed.engine, "SELECT receipt_number FROM refund_operations")
    assert len(receipt) == 1
    assert said[-2:] == ["A staff member is reviewing your request.", f"Your refund is done: receipt {receipt[0][0]}."]
    assert rows(resumed.engine, "SELECT attempts FROM agent_notices WHERE delivered_at IS NOT NULL") == [(1,)]
    after = resumed.browser("d01-ana").get("/api/mode").json()
    assert after["paused"] is None and after["decisions_waiting"] == 0


def test_a_decision_whose_delivery_failed_three_times_gets_new_attempts_at_a_restart(server):
    script = [line for line in SCRIPT if line != SCRIPT[2]]  # no message is sent while the provider is down
    s = server(1.0, script)
    ana, rui = s.browser("d01-ana"), s.browser("d01-rui")
    conversation = ana.post("/api/conversations").json()["conversation_id"]
    ana.post(f"/api/conversations/{conversation}/messages", {"text": DEVELOPMENT["D01"].customer.opening_message})
    proposal = ana.get(f"/api/conversations/{conversation}").json()["proposals"][0]["proposal_id"]
    ana.post(f"/api/proposals/{proposal}/confirmation", {"decision": "confirmed"})
    s.agent.model.respond = lambda *a: (_ for _ in ()).throw(RuntimeError("provider down"))  # an outage
    rui.post(f"/api/staff/proposals/{proposal}/decision", {"decision": "approved"})
    for _ in range(notices.MAX_ATTEMPTS - 1):
        notices.deliver_pending(s.engine, s.agent, s.clock)
    assert rows(s.engine, "SELECT attempts, delivered_at FROM agent_notices") == [(notices.MAX_ATTEMPTS, None)]
    assert notices.deliver_pending(s.engine, s.agent, s.clock) == 0  # given up: no endless calls

    assert live.retry_stuck_notices(s.engine) == 1
    resumed = server(1.0, script)
    assert notices.deliver_pending(resumed.engine, resumed.agent, resumed.clock) == 1
    assert rows(resumed.engine, "SELECT count(*) FROM refund_operations") == [(1,)]


def test_the_mode_door_in_mock_mode_names_the_script_and_no_budget(db):
    scenario = DEVELOPMENT["D01"]
    seed(db("owner"), scenario, POLICY)
    engine = db("app")
    connection = database.checkpoint_connection("app", engine.url.database)
    try:
        agent = Agent(engine, POLICY, ScriptedModel(SCRIPT), PostgresSaver(connection), Clock(scenario.now))
        mode = Browser(create_app(engine, POLICY, Clock(scenario.now), agent=agent)).get("/api/mode").json()
    finally:
        connection.close()
    assert mode == {
        "agent": "scripted",
        "model": None,
        "payments": "simulated",
        "budget": None,
        "paused": None,
        "decisions_waiting": 0,
    }


def test_a_budget_given_more_than_a_session_may_spend_is_refused(db):
    with pytest.raises(ValueError, match="at most"):
        live.session_budget(db("app"), live.MOST_USD + 1)
    assert isinstance(live.session_budget(db("app"), 0.5), Budget)
