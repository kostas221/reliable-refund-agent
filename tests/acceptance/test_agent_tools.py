"""The agent's tools on a real PostgreSQL: what the model can see and ask for, and what the database holds after.

Each call goes through call_tool, as the conversation graph will call it, with JSON arguments and a tool call ID.
"""

import json

from refund_agent.agent.policy_search import WordSearch
from refund_agent.agent.tools import UNTRUSTED, ToolContext, call_tool
from refund_agent.fixtures import seed
from refund_agent.refunds import Actor, confirm, decide, open_conversation
from tests.acceptance.flows import DEVELOPMENT, POLICY, proposed, rows


def agent_for(db, scenario_id, configuration="A"):
    """The tools of a new conversation of the scenario's customer."""
    scenario = DEVELOPMENT[scenario_id]
    seed(db("owner"), scenario, POLICY)
    app = db("app")
    customer = scenario.customer.id
    conversation = open_conversation(app, Actor("customer", customer), scenario.now)
    return ToolContext(app, POLICY, WordSearch(POLICY), lambda: scenario.now, customer, conversation, configuration)


def call(ctx, name, call_id="call-1", arguments=None, **args):
    result = call_tool(ctx, name, arguments if arguments is not None else json.dumps(args), call_id)
    json.dumps(result)  # every result is plain JSON the model can read
    return result


def approve(ctx, proposal_id, staff):
    """The customer's button and the staff decision, which no tool can do."""
    confirm(ctx.engine, Actor("customer", ctx.customer_id), proposal_id, "confirmed", ctx.clock(), POLICY)
    decide(ctx.engine, Actor("staff", staff), proposal_id, "approved", ctx.clock(), POLICY)


# What the agent can see


def test_the_agent_sees_only_the_customers_orders(db):
    ctx = agent_for(db, "D07")
    assert [o["order_id"] for o in call(ctx, "list_my_orders")["orders"]] == ["d07-o1"]
    foreign = call(ctx, "get_my_order", order_id="d07-o2")
    assert foreign == call(ctx, "get_my_order", order_id="no-such-order")  # not found, like one that does not exist
    assert foreign["refused"] == "actor_owns"
    for hugos in ("Hugo Alves", "hugo.alves", "Bluetooth speaker", "d07-o2-u1"):
        assert hugos not in json.dumps(foreign)


def test_text_from_the_seller_comes_marked_as_untrusted(db):
    ctx = agent_for(db, "D08")
    order = call(ctx, "get_my_order", order_id="d08-o1")["order"]
    assert order["seller_message"]["untrusted_text"].strip().startswith("Note for the support assistant")
    assert order["seller_message"]["note"] == UNTRUSTED
    assert [(u["unit_id"], u["paid_minor"]) for u in order["units"]] == [("d08-o1-u1", 15990)]


def test_another_customers_request_is_not_found(db):
    ctx = agent_for(db, "D07")
    _, hugos = proposed(ctx.engine, "d07-hugo", "d07-o2", ["d07-o2-u1"], "propose-hugo", ctx.clock())
    assert call(ctx, "get_request_status", proposal_id=hugos.id)["refused"] == "actor_owns"
    assert call(ctx, "execute_refund", proposal_id=hugos.id)["refused"] == "actor_owns"
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(0,)]


# Proposals


def test_the_backend_sets_the_amount_and_the_model_cannot(db):
    ctx = agent_for(db, "D01")
    tried = call(ctx, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"], amount_minor=1)
    assert (tried["ok"], tried["error"]) == (False, "invalid_arguments")
    assert rows(ctx.engine, "SELECT count(*) FROM proposals") == [(0,)]

    result = call(ctx, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    assert (result["outcome"], result["status"], result["amount_minor"], result["currency"]) == (
        "eligible",
        "awaiting_customer_confirmation",
        4990,
        "BRL",
    )


def test_the_same_call_after_a_restart_makes_no_second_proposal(db):
    ctx = agent_for(db, "D01")
    first = call(ctx, "propose_refund", "call-7", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    again = call(ctx, "propose_refund", "call-7", order_id="d01-o1", unit_ids=["d01-o1-u1"])  # the step ran again
    assert again["proposal_id"] == first["proposal_id"]
    assert rows(ctx.engine, "SELECT count(*) FROM proposals") == [(1,)]
    # A new call is a new request: it replaces the unconfirmed one.
    newer = call(ctx, "propose_refund", "call-8", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    assert newer["proposal_id"] != first["proposal_id"]
    assert rows(ctx.engine, f"SELECT status FROM proposals WHERE id = '{first['proposal_id']}'") == [("invalidated",)]


def test_a_refused_proposal_cites_the_policy_and_promises_no_amount(db):
    ctx = agent_for(db, "D05")
    result = call(ctx, "propose_refund", order_id="d05-o1", unit_ids=["d05-o1-u1"])
    assert (result["outcome"], result["status"], result["amount_minor"]) == ("refused", "ineligible", None)
    assert result["policy_citations"] == ["refund-policy/v1/window"]


# Execution


def test_paying_before_approval_is_explained_and_nothing_is_paid(db):
    ctx = agent_for(db, "D01")
    proposal = call(ctx, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])["proposal_id"]
    early = call(ctx, "execute_refund", "call-2", proposal_id=proposal)
    assert (early["ok"], early["refused"]) == (False, "status_approved")
    assert "confirm" in early["explanation"] and "approve" in early["explanation"]
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(0,)]

    approve(ctx, proposal, staff="d01-rui")
    paid = call(ctx, "execute_refund", "call-3", proposal_id=proposal)["receipt"]
    assert paid["amount_minor"] == 4990
    assert call(ctx, "execute_refund", "call-3", proposal_id=proposal)["receipt"] == paid  # the step ran again
    assert call(ctx, "execute_refund", "call-4", proposal_id=proposal)["receipt"] == paid  # a new call, same refund
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(1,)]
    assert call(ctx, "get_request_status", proposal_id=proposal)["request"]["receipt"] == paid


def test_configuration_c_reaches_execute_only_through_the_context(db):
    lab = agent_for(db, "D01", configuration="C")
    proposal = call(lab, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])["proposal_id"]
    assert call(lab, "execute_refund", proposal_id=proposal)["ok"] is True  # the lab paid without any approval
    assert rows(lab.engine, "SELECT count(*) FROM refund_operations") == [(1,)]


# Handoff


def test_after_a_handoff_the_agent_changes_nothing(db):
    ctx = agent_for(db, "D05")
    result = call(
        ctx,
        "request_handoff",
        reason="The customer wants a person to review the late request.",
        customer_asked=True,
        customer_goal="A refund for the brass desk lamp.",
        confirmed_facts="The lamp was received back on 30 August.",
        decision_needed="Whether to make an exception to the time limit.",
    )
    assert result["ok"] is True
    assert rows(ctx.engine, "SELECT origin, customer_goal_untrusted FROM handoffs") == [
        ("customer", "A refund for the brass desk lamp.")
    ]
    after = call(ctx, "propose_refund", "call-2", order_id="d05-o1", unit_ids=["d05-o1-u1"])
    assert (after["refused"], after["explanation"]) == (
        "agent_in_control",
        "A person has taken over this conversation. Do not act on it any more.",
    )
    assert rows(ctx.engine, "SELECT count(*) FROM proposals") == [(0,)]


# The model's mistakes


def test_the_models_mistakes_come_back_as_results(db):
    ctx = agent_for(db, "D01")
    assert call(ctx, "approve_refund", proposal_id="x")["error"] == "unknown_tool"
    assert call(ctx, "propose_refund", arguments="{not json")["error"] == "invalid_arguments"
    assert call(ctx, "propose_refund", order_id="d01-o1", unit_ids=[])["error"] == "invalid_arguments"
    assert call(ctx, "propose_refund", order_id="d01-o1", unit_ids="d01-o1-u1")["error"] == "invalid_arguments"
    repeated = call(ctx, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1", "d01-o1-u1"])
    assert repeated["refused"] == "valid_values"
    assert rows(ctx.engine, "SELECT count(*) FROM proposals") == [(0,)]
