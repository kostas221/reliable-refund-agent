"""The conversation graph on a real PostgreSQL, with the scripted model: whole runs, restarts, a crash right after a
refund, an event that claims an approval, a handoff and an agent that never answers (plan sections 5 and 13).
"""

import json

import pytest
from langgraph.checkpoint.postgres import PostgresSaver

from refund_agent import db as database
from refund_agent.agent import graph as graph_module
from refund_agent.agent.graph import Agent, AgentLoopError
from refund_agent.agent.model import Call, ModelTurn, Say, ScriptedModel
from refund_agent.evaluation.evaluator import capture_baseline, evaluate
from refund_agent.fixtures import seed
from refund_agent.refunds import Actor, confirm, decide, open_conversation
from tests.acceptance.flows import DEVELOPMENT, POLICY, rows
from tests.acceptance.test_scripted_agent import ANA_MUG

D01 = DEVELOPMENT["D01"]


class Shop:
    """A seeded database and agents on it; each agent gets its own checkpoint connection, like a new process."""

    def __init__(self, db, scenario_id):
        self.db, self.scenario = db, DEVELOPMENT[scenario_id]
        seed(db("owner"), self.scenario, POLICY)
        self.app = db("app")
        self.baseline = capture_baseline(self.app)
        self.connections = []
        customer = Actor("customer", self.scenario.customer.id)
        self.conversation = open_conversation(self.app, customer, self.scenario.now)

    def agent(self, script, engine=None, model=None, **options):
        connection = database.checkpoint_connection("app", self.app.url.database)
        self.connections.append(connection)
        model = model or ScriptedModel(script)
        engine = engine or self.app
        return Agent(engine, POLICY, model, PostgresSaver(connection), lambda: self.scenario.now, **options), model

    def approve(self, proposal_id):
        """The customer's button and the staff decision, outside the agent."""
        now = self.scenario.now
        confirm(self.app, Actor("customer", self.scenario.customer.id), proposal_id, "confirmed", now, POLICY)
        decide(self.app, Actor("staff", self.scenario.fixture.staff[0].id), proposal_id, "approved", now, POLICY)

    def said(self):
        return rows(self.app, "SELECT author, content_untrusted FROM messages ORDER BY created_at, id")


@pytest.fixture
def shop(db):
    shops = []

    def make(scenario_id="D01"):
        shops.append(Shop(db, scenario_id))
        return shops[-1]

    yield make
    for opened in shops:
        for connection in opened.connections:
            connection.close()


def proposal_of(agent, conversation):
    return next(json.loads(m["content"]) for m in agent.messages(conversation) if m.get("name") == "propose_refund")[
        "proposal_id"
    ]


def test_a_whole_conversation_runs_through_the_graph_and_the_evaluator_passes_it(shop):
    s = shop()
    agent, _ = s.agent(ANA_MUG)
    first = agent.receive(s.conversation, D01.customer.opening_message)
    assert first[-1]["text"] == "I can refund R$ 49,90 for the blue mug. Please confirm on the proposal card."
    proposal = proposal_of(agent, s.conversation)
    s.approve(proposal)
    last = agent.notify(s.conversation, f"Request {proposal} was approved by a staff member.")
    receipt = rows(s.app, "SELECT receipt_number FROM refund_operations")[0][0]
    assert last[-1]["text"] == f"Your refund of R$ 49,90 is done: receipt {receipt}."

    # What the customer and the agent said is in the messages table, which the screens and the evaluator read.
    assert s.said() == [
        ("customer", D01.customer.opening_message),
        ("agent", "I can refund R$ 49,90 for the blue mug. Please confirm on the proposal card."),
        ("agent", f"Your refund of R$ 49,90 is done: receipt {receipt}."),
    ]
    verdict = evaluate(D01, s.app, s.baseline)
    assert verdict.names("failed") == [], verdict.report()
    assert verdict.with_audit({name: "passed" for name in verdict.names("pending")}).result == "passed"
    assert len(agent.usage(s.conversation)) == len(ANA_MUG)  # one entry per model request


def test_the_conversation_survives_a_restart(shop, db):
    s = shop()
    before, _ = s.agent(ANA_MUG)
    before.receive(s.conversation, D01.customer.opening_message)
    remembered = before.messages(s.conversation)
    said = s.said()
    s.app.dispose()  # the process stops; a new one starts with new connections

    after, model = s.agent(ANA_MUG, engine=db("app"))
    assert after.messages(s.conversation) == remembered
    proposal = proposal_of(after, s.conversation)
    s.approve(proposal)
    after.notify(s.conversation, f"Request {proposal} was approved by a staff member.")
    assert model.requests[0]["messages"][: len(remembered)] == remembered  # the model saw the whole conversation
    assert rows(s.app, "SELECT count(*) FROM refund_operations") == [(1,)]
    assert s.said()[: len(said)] == said and len(s.said()) == len(said) + 1  # nothing written twice


def test_a_crash_after_the_refund_and_before_the_checkpoint_pays_once(shop, monkeypatch):
    # Failure case 6, the graph's part: the refund commits, then the process dies before the step is saved.
    s = shop()
    agent, _ = s.agent(ANA_MUG)
    agent.receive(s.conversation, D01.customer.opening_message)
    proposal = proposal_of(agent, s.conversation)
    s.approve(proposal)
    real_call_tool = graph_module.call_tool

    def dies_after_paying(ctx, name, arguments, call_id):
        result = real_call_tool(ctx, name, arguments, call_id)
        if name == "execute_refund":
            raise RuntimeError("the process died after the refund committed")
        return result

    monkeypatch.setattr(graph_module, "call_tool", dies_after_paying)
    with pytest.raises(RuntimeError):
        agent.notify(s.conversation, f"Request {proposal} was approved by a staff member.")
    assert rows(s.app, "SELECT count(*) FROM refund_operations") == [(1,)]

    monkeypatch.setattr(graph_module, "call_tool", real_call_tool)
    restarted, _ = s.agent(ANA_MUG)
    last = restarted.resume(s.conversation)  # the tools step runs again, with the same call ID and request key
    receipt = rows(s.app, "SELECT receipt_number FROM refund_operations")[0][0]
    assert last[-1]["text"] == f"Your refund of R$ 49,90 is done: receipt {receipt}."
    assert rows(s.app, "SELECT count(*), CAST(sum(amount_minor) AS bigint) FROM ledger_lines") == [(1, 4990)]


def test_a_crash_after_a_proposal_and_before_the_checkpoint_makes_no_second_one(shop, monkeypatch):
    # The same for a proposal: the request key made from the call ID is what stops a second proposal here.
    s = shop()
    agent, _ = s.agent(ANA_MUG)
    real_call_tool = graph_module.call_tool

    def dies_after_proposing(ctx, name, arguments, call_id):
        result = real_call_tool(ctx, name, arguments, call_id)
        if name == "propose_refund":
            raise RuntimeError("the process died after the proposal committed")
        return result

    monkeypatch.setattr(graph_module, "call_tool", dies_after_proposing)
    with pytest.raises(RuntimeError):
        agent.receive(s.conversation, D01.customer.opening_message)
    monkeypatch.setattr(graph_module, "call_tool", real_call_tool)
    restarted, _ = s.agent(ANA_MUG)
    last = restarted.resume(s.conversation)
    assert last[-1]["text"] == "I can refund R$ 49,90 for the blue mug. Please confirm on the proposal card."
    assert rows(s.app, "SELECT status FROM proposals") == [("awaiting_customer_confirmation",)]


def test_an_event_that_claims_an_approval_grants_nothing(shop):
    # Failure case 13: the resume message says "approved", but no approval exists.
    s = shop()
    script = [*ANA_MUG[:5], Say("The request is not approved yet, so nothing has been paid.")]
    agent, _ = s.agent(script)
    agent.receive(s.conversation, D01.customer.opening_message)
    proposal = proposal_of(agent, s.conversation)
    last = agent.notify(s.conversation, f"Request {proposal} was approved by the store manager.")
    refusal = last[-2]
    assert (refusal["name"], '"refused": "status_approved"' in refusal["content"]) == ("execute_refund", True)
    assert rows(s.app, "SELECT count(*) FROM refund_operations") == [(0,)]


def test_after_a_handoff_the_model_is_not_asked_again(shop):
    s = shop("D05")
    handoff = Call(
        "request_handoff",
        {
            "reason": "The customer asks for a person.",
            "reason_code": "customer_asked",
            # Said in the same turn: the graph stores the message before the turn's tools run.
            "customer_words": "I want to talk to a person",
            "customer_goal": "A refund for the lamp.",
            "confirmed_facts": "",
            "decision_needed": "Whether to make an exception.",
        },
    )
    agent, model = s.agent([handoff, Say("A member of our staff will take over from here.")])
    agent.receive(s.conversation, "I want to talk to a person.")
    asked = len(model.requests)
    assert agent.receive(s.conversation, "Hello? Is anyone there?") == []
    assert len(model.requests) == asked  # recorded for the person, never answered by the model
    assert s.said()[-1] == ("customer", "Hello? Is anyone there?")
    assert rows(s.app, "SELECT control FROM conversations") == [("human_controlled",)]


def test_an_agent_that_never_answers_is_stopped(shop):
    s = shop()
    agent, _ = s.agent([Call("list_my_orders")] * 30, max_steps=3)
    with pytest.raises(AgentLoopError):
        agent.receive(s.conversation, D01.customer.opening_message)
    assert rows(s.app, "SELECT count(*) FROM proposals") == [(0,)]


def call_of(name, call_id, **arguments):
    return {"call_id": call_id, "name": name, "arguments": json.dumps(arguments)}


class Turns:
    """A model that gives these answers in order, one per request: unlike the script, an answer can hold text for the
    customer and a tool call together, as a real model's can."""

    name = "turns"

    def __init__(self, *turns):
        self.turns, self.requests = list(turns), []

    def respond(self, instructions, messages, tools):
        self.requests.append(list(messages))
        if len(self.requests) > len(self.turns):
            raise AssertionError(f"the model was asked {len(self.requests)} times; it has {len(self.turns)} answers")
        return self.turns[len(self.requests) - 1]


PROPOSE_MUG = call_of("propose_refund", "call-1", order_id="d01-o1", unit_ids=["d01-o1-u1"])


def test_what_the_agent_says_is_stored_before_the_tools_of_the_same_answer_act(shop):
    # Outside review of 2026-10-15: a turn's messages were stored when the turn ended, after its actions, so a question
    # and a proposal could not be put in order. Each step now stores what was said before the next step runs. Text
    # that asks nothing goes on to the tools of its answer; a question ends the turn (the tests below).
    s = shop()
    model = Turns(
        ModelTurn(text="Let me record that for you.", tool_calls=(PROPOSE_MUG,)),
        ModelTurn(text="Please confirm on the card below."),
    )
    agent, _ = s.agent([], model=model)
    agent.receive(s.conversation, "Please refund my mug.")
    order = rows(
        s.app,
        "SELECT kind FROM (SELECT seq AS place, 'said: ' || content_untrusted AS kind FROM messages "
        "UNION ALL SELECT id, 'did: ' || event FROM audit_events WHERE event = 'propose') x ORDER BY place",
    )
    assert order == [
        ("said: Please refund my mug.",),
        ("said: Let me record that for you.",),
        ("did: propose",),
        ("said: Please confirm on the card below.",),
    ]


# A question to the customer ends the agent's turn (plan change log, 2026-10-23)


def not_run(agent, conversation):
    return [
        (m["call_id"], json.loads(m["content"])["not_run"])
        for m in agent.messages(conversation)
        if m["role"] == "tool" and "not_run" in json.loads(m["content"])
    ]


@pytest.mark.parametrize(
    "call, table",
    [
        (PROPOSE_MUG, "proposals"),
        (
            call_of(  # a handoff the backend accepts here (d01-o1 is recorded as delivered): only the brake stops it
                "request_handoff",
                "call-1",
                reason_code="delivery_disputed",
                order_id="d01-o1",
                reason="Delivery.",
                customer_goal="",
                confirmed_facts="",
                decision_needed="",
            ),
            "handoffs",
        ),
        (call_of("assess_refund", "call-1", order_id="d01-o1", unit_ids=["d01-o1-u1"]), "proposals"),
    ],
    ids=["proposal", "handoff", "read"],
)
def test_a_question_ends_the_turn_and_the_calls_given_with_it_do_not_run(shop, call, table):
    # D33 tries 1 and 3 of 2026-10-22: the question went to the customer with a call, the graph went on, and the agent
    # proposed before the customer answered. A read is held back too: after it the agent would speak again.
    s = shop()
    model = Turns(ModelTurn(text="Which mug do you mean?", tool_calls=(call,)), ModelTurn(text="Thank you."))
    agent, _ = s.agent([], model=model)
    agent.receive(s.conversation, "Please refund my mug.")
    assert len(model.requests) == 1  # the turn ended at the question: the model was not asked again
    assert rows(s.app, f"SELECT count(*) FROM {table}") == [(0,)]
    assert not_run(agent, s.conversation) == [("call-1", "question_to_customer")]
    assert s.said() == [("customer", "Please refund my mug."), ("agent", "Which mug do you mean?")]
    agent.receive(s.conversation, "The blue one.")
    assert '"not_run": "question_to_customer"' in model.requests[1][-2]["content"]  # the model sees what did not run
    assert rows(s.app, f"SELECT count(*) FROM {table}") == [(0,)]


D33_QUESTION = (  # D33 try 1 of runs/pilot-20261022T165428Z-gpt-6-luna-none, with its assessment call
    "I found two returned white ceramic planters, one in each order. Which would you like refunded: the one in order "
    "d33-o2 or the one in order d33-o1?"
)


def test_the_customers_answer_to_the_question_lets_the_proposal_through(shop):
    s = shop("D33")
    second = call_of("propose_refund", "call-2", order_id="d33-o2", unit_ids=["d33-o2-u1"])
    model = Turns(
        ModelTurn(
            text=D33_QUESTION,
            tool_calls=(call_of("assess_refund", "call-1", order_id="d33-o2", unit_ids=["d33-o2-u1"]),),
        ),
        ModelTurn(text="", tool_calls=(second,)),
        ModelTurn(text="Please confirm the proposal on its card."),
    )
    agent, _ = s.agent([], model=model)
    agent.receive(s.conversation, s.scenario.customer.opening_message)
    assert rows(s.app, "SELECT count(*) FROM proposals") == [(0,)]
    agent.receive(s.conversation, "The one from my order of 5 October.")
    units = "SELECT p.status, pu.order_unit_id FROM proposals p JOIN proposal_units pu ON pu.proposal_id = p.id"
    assert rows(s.app, units) == [("awaiting_customer_confirmation", "d33-o2-u1")]


def test_an_instruction_without_a_question_mark_is_stopped_by_the_selection_check(shop):
    # The review of 2026-10-23: "Please choose ..." asks for input with no question mark, so the graph lets its call
    # run; the backend refuses a proposal among look-alikes until the customer's words say which.
    s = shop("D33")
    choose = "Please choose the planter from order d33-o1 or order d33-o2."
    model = Turns(
        ModelTurn(
            text=choose, tool_calls=(call_of("propose_refund", "call-1", order_id="d33-o2", unit_ids=["d33-o2-u1"]),)
        ),
        ModelTurn(text=choose),
    )
    agent, _ = s.agent([], model=model)
    agent.receive(s.conversation, s.scenario.customer.opening_message)
    assert rows(s.app, "SELECT count(*) FROM proposals") == [(0,)]
    assert '"refused": "units_named"' in model.requests[1][-1]["content"]


def test_a_crash_before_the_held_calls_are_marked_runs_none_of_them_after_a_restart(shop, monkeypatch):
    # The turn's answer is saved before its calls are marked as not run. A crash in between leaves the run to be
    # finished; the next message finishes it first, and the held call still does not run.
    s = shop()

    def dies(state):
        raise RuntimeError("the process died before the held calls were marked")

    monkeypatch.setattr(Agent, "_hold", staticmethod(dies))
    first = Turns(ModelTurn(text="Which mug do you mean?", tool_calls=(PROPOSE_MUG,)))
    agent, _ = s.agent([], model=first)
    with pytest.raises(RuntimeError):
        agent.receive(s.conversation, "Please refund my mug.")
    monkeypatch.undo()  # a new process, with the real node
    later = Turns(ModelTurn(text="Thank you, I will look at the blue mug."))
    restarted, _ = s.agent([], model=later)
    restarted.receive(s.conversation, "The blue one.")
    assert rows(s.app, "SELECT count(*) FROM proposals") == [(0,)]
    assert not_run(restarted, s.conversation) == [("call-1", "question_to_customer")]  # marked once, never run
    assert [m["role"] for m in later.requests[0][-3:]] == ["agent", "tool", "customer"]


def test_a_notice_while_a_question_waits_still_pays_the_approved_request(shop):
    # A question waits for the customer's answer about its own subject; it does not stop the payment of a request the
    # customer confirmed and a staff member approved.
    s = shop()
    model = Turns(
        ModelTurn(text="", tool_calls=(PROPOSE_MUG,)),
        ModelTurn(text="Please confirm the proposal on its card."),
        ModelTurn(text="Which other order do you mean?", tool_calls=(call_of("list_my_orders", "call-3"),)),
        ModelTurn(text="", tool_calls=(call_of("execute_refund", "call-4"),)),
        ModelTurn(text="Your refund is done."),
    )
    agent, _ = s.agent([], model=model)
    agent.receive(s.conversation, "Please refund my mug.")
    s.approve(proposal_of(agent, s.conversation))
    agent.receive(s.conversation, "Can you also look at my other order?")
    assert not_run(agent, s.conversation) == [("call-3", "question_to_customer")]
    agent.notify(s.conversation, "The request was confirmed and approved, so it is ready to be paid.")
    assert rows(s.app, "SELECT count(*) FROM refund_operations") == [(1,)]


def test_checkpoints_live_apart_from_the_business_tables(shop):
    s = shop()
    tables = rows(
        s.app,
        "SELECT table_schema, table_name FROM information_schema.tables WHERE table_name LIKE 'checkpoint%' ORDER BY 2",
    )
    assert {schema for schema, _ in tables} == {"graph"}
    assert {name for _, name in tables} >= {"checkpoints", "checkpoint_blobs", "checkpoint_writes"}


def test_the_fact_line_follows_an_answer_that_states_a_paid_refund_without_its_section(shop):
    # D20 of Luna none, 2026-10-23: the receipt of a refund paid before the conversation, told without the section on
    # refunding each unit once. The graph says the line after the answer, marked as its own; the model's next turn is
    # its next scripted line, and the section, once said, is not said again (review of the model comparison).
    s = shop("D20")
    agent, model = s.agent(
        (
            Call("list_my_orders"),
            Say("Both items were already refunded: BRL 157.90, receipt R-H10-0001."),
            Say("The receipt number is R-H10-0001."),
        )
    )
    first = agent.receive(s.conversation, "Hello, I returned the desk fan and the tablet stand. When is my refund?")
    answer, line = first[-2:]
    assert answer["text"] == "Both items were already refunded: BRL 157.90, receipt R-H10-0001." and not answer.get(
        "fact_line"
    )
    assert line["fact_line"] is True and line["text"].endswith("cannot be refunded again (refund-policy/v2/remaining).")
    second = agent.receive(s.conversation, "Could you give me the receipt number, please?")
    assert [m["text"] for m in second if m["role"] == "agent"] == ["The receipt number is R-H10-0001."]
    assert [author for author, _ in s.said()] == ["customer", "agent", "agent", "customer", "agent"]
    assert len(model.requests) == 3  # the line asked the model nothing
    verdict = evaluate(s.scenario, s.app, s.baseline)
    # Shown, so not failed; D20 states its obligation, so the reader checks it (the citation rule of v1.2).
    cited = next(item for item in verdict.items if item.name == "cites:refund-policy/v2/remaining")
    assert cited.status == "pending" and cited.evidence.startswith("shown; the reader checks that it told:")


def test_no_fact_line_cuts_in_between_an_answer_and_its_tool_calls(shop):
    # The line follows only an answer with no calls: after one with calls it would come last, and the calls would never
    # run, since routing follows the last message (review of the model comparison, 2026-10-24).
    s = shop("D20")
    model = Turns(
        ModelTurn(text="", tool_calls=(call_of("list_my_orders", "call-1"),)),
        ModelTurn(
            text="Both items were refunded, receipt R-H10-0001. Let me check the order.",
            tool_calls=(call_of("get_my_order", "call-2", order_id="h10-o1"),),
        ),
        ModelTurn(text="They cannot be refunded again (refund-policy/v2/remaining)."),
    )
    agent, _ = s.agent((), model=model)
    agent.receive(s.conversation, "When do I get my refund for the fan and the stand?")
    tools = [m.get("name") for m in agent.messages(s.conversation) if m["role"] == "tool"]
    assert tools == ["list_my_orders", "get_my_order"]
    assert not any(m.get("fact_line") for m in agent.messages(s.conversation))
