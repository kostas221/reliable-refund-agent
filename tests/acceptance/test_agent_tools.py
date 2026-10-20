"""The agent's tools on a real PostgreSQL: what the model can see and ask for, and what the database holds after.

Each call goes through call_tool, as the conversation graph will call it, with JSON arguments and a tool call ID.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from refund_agent.agent.policy_search import WordSearch
from refund_agent.agent.tools import UNTRUSTED, ToolContext, call_tool
from refund_agent.fixtures import seed
from refund_agent.refunds import Actor, confirm, decide, open_conversation
from tests.acceptance.flows import DEVELOPMENT, POLICY, SCENARIOS, policy_of, proposed, rows


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


# Every fixture, before the final evaluation


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_every_tool_answers_on_every_fixture(db, scenario_id):
    """A paid run must not stop on a fixture shape the development set lacks (an order not delivered, two payments,
    a second customer): every read, and a proposal for each unit alone, own or not, answers with a result or a
    refusal, never an error."""
    scenario = SCENARIOS[scenario_id]
    policy = policy_of(scenario)
    seed(db("owner"), scenario, policy)
    app = db("app")
    customer = scenario.customer.id

    def tools() -> ToolContext:
        conversation = open_conversation(app, Actor("customer", customer), scenario.now)
        return ToolContext(app, policy, WordSearch(policy), lambda: scenario.now, customer, conversation)

    listed = call(tools(), "list_my_orders")
    assert sorted(o["order_id"] for o in listed["orders"]) == sorted(scenario.agent_visible_orders)
    for order in scenario.fixture.orders:
        own = order.customer == customer
        assert call(tools(), "get_my_order", order_id=order.id)["ok"] == own, order.id
        for unit in order.units:
            answer = call(tools(), "propose_refund", order_id=order.id, unit_ids=[unit.id])
            assert answer["ok"] if own else answer.get("refused") == "actor_owns", answer


# What the agent can see


def test_the_agent_sees_only_the_customers_orders(db):
    ctx = agent_for(db, "D07")
    assert [o["order_id"] for o in call(ctx, "list_my_orders")["orders"]] == ["d07-o1"]
    foreign = call(ctx, "get_my_order", order_id="d07-o2")
    assert foreign == call(ctx, "get_my_order", order_id="no-such-order")  # not found, like one that does not exist
    assert foreign["refused"] == "actor_owns"
    for hugos in ("Hugo Alves", "hugo.alves", "Bluetooth speaker", "d07-o2-u1"):
        assert hugos not in json.dumps(foreign)


def test_text_from_the_seller_comes_marked_as_untrusted_in_both_reads(db):
    # The list carries it too: in every pilot conversation of D08 the agent read only the list, so a message shown
    # only by get_my_order never reached it.
    ctx = agent_for(db, "D08")
    (listed,) = call(ctx, "list_my_orders")["orders"]
    order = call(ctx, "get_my_order", order_id="d08-o1")["order"]
    assert listed == order
    assert order["seller_message"]["untrusted_text"].strip().startswith("Note for the support assistant")
    assert order["seller_message"]["note"] == UNTRUSTED
    assert [(u["unit_id"], u["paid_minor"]) for u in order["units"]] == [("d08-o1-u1", 15990)]


def test_an_order_without_a_seller_message_has_no_such_field(db):
    (order,) = call(agent_for(db, "D01"), "list_my_orders")["orders"]
    assert "seller_message" not in order


def test_the_agent_sees_the_customers_earlier_requests(db):
    # D10: the customer says she confirmed a request before. The order shows it, expired, never paid.
    ctx = agent_for(db, "D10")
    (order,) = call(ctx, "list_my_orders")["orders"]
    assert order["requests"] == [
        {
            "proposal_id": "d10-p1",
            "status": "expired",
            "amount_minor": 8990,
            "unit_ids": ["d10-o1-u1"],
            "created_at": "2026-09-11T09:00:00+00:00",
            "receipt_number": None,
            "rejection_reason": None,
        }
    ]
    assert call(ctx, "get_my_order", order_id="d10-o1")["order"]["requests"] == order["requests"]


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
    assert result["policy_citations"] == ["refund-policy/v2/window"]


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
        reason_code="customer_asked",
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


# The agent hands off only for a case the policy names (policy v2, section exceptions; v1.1 step 3)


def handoff(ctx, code, order_id="", call_id="hand-1", units=()):
    return call(
        ctx,
        "request_handoff",
        call_id,
        reason_code=code,
        order_id=order_id,
        unit_ids=list(units),
        reason="A test of the handoff check.",
        customer_goal="",
        confirmed_facts="",
        decision_needed="",
    )


def control(ctx):
    return rows(ctx.engine, f"SELECT control FROM conversations WHERE id = '{ctx.conversation_id}'")


def test_a_delivery_dispute_needs_an_order_recorded_as_delivered(db):
    ctx = agent_for(db, "D15")  # h05-o1 was delivered; h05-o2, the controller, is still on its way
    refused = handoff(ctx, "delivery_disputed", "h05-o2")
    assert (refused["ok"], refused["refused"]) == (False, "handoff_reason")
    assert "not recorded as delivered" in refused["explanation"]
    # An order on its way is answered with its status, and cancelling it is offered to a person (eligible-orders).
    assert "offer a person for that (refund-policy/v2/eligible-orders)" in refused["explanation"]
    assert control(ctx) == [("agent",)]  # nothing changed, and the refusal is in the audit log
    assert rows(ctx.engine, "SELECT outcome, reason FROM audit_events WHERE event = 'hand_off'") == [
        ("rejected", "handoff_reason")
    ]
    assert handoff(ctx, "delivery_disputed", "h05-o1", "hand-2")["ok"] is True
    assert control(ctx) == [("human_controlled",)]


def test_a_decision_of_the_shop_must_have_been_made_in_this_conversation(db):
    ctx = agent_for(db, "D10")
    assert handoff(ctx, "shop_decided")["refused"] == "handoff_reason"
    proposal = call(ctx, "propose_refund", "p-1", order_id="d10-o1", unit_ids=["d10-o1-u1"])
    assert proposal["outcome"] == "needs_person"
    # The result names the code, so a decision of the shop is not handed off as the customer's request.
    assert "reason_code shop_decided" in proposal["next_step"]
    assert handoff(ctx, "shop_decided", call_id="hand-2")["ok"] is True
    reason = "shop_decided: A test of the handoff check."  # the staff member sees the case named
    assert rows(ctx.engine, "SELECT origin, reason FROM handoffs") == [("agent", reason)]


def test_a_decision_of_the_shop_is_the_latest_of_the_conversation_on_the_order_as_it_is(db):
    # An earlier referral is not standing permission: the request in front of the agent is the latest decision.
    ctx = agent_for(db, "D02")  # delivered 8 September 12:00, so the deadline is 8 October 12:00
    bowl, plate = "d02-o1-u1", "d02-o1-u2"
    assert call(ctx, "propose_refund", "p-1", order_id="d02-o1", unit_ids=[bowl])["outcome"] == "eligible"
    late = replace(ctx, clock=lambda: datetime(2026, 10, 9, 12, 0, tzinfo=UTC))  # the bowl's proposal lapsed
    assert call(late, "propose_refund", "p-2", order_id="d02-o1", unit_ids=[bowl])["outcome"] == "needs_person"
    assert call(late, "propose_refund", "p-3", order_id="d02-o1", unit_ids=[plate])["outcome"] == "refused"
    refused = handoff(late, "shop_decided")
    assert refused["refused"] == "handoff_reason"
    assert "For a refund request, call propose_refund and follow its result." in refused["explanation"]
    assert call(late, "propose_refund", "p-4", order_id="d02-o1", unit_ids=[bowl])["outcome"] == "needs_person"
    with db("owner").begin() as conn:  # for example, a corrected return record
        conn.execute(text("UPDATE orders SET material_version = material_version + 1 WHERE id = 'd02-o1'"))
    assert handoff(late, "shop_decided", call_id="hand-2")["refused"] == "handoff_reason"  # decided on the old order
    assert call(late, "propose_refund", "p-5", order_id="d02-o1", unit_ids=[bowl])["outcome"] == "needs_person"
    assert handoff(late, "shop_decided", call_id="hand-3")["ok"] is True


def test_a_refused_handoff_keeps_the_refund_under_way_and_says_what_to_do_instead(db):
    ctx = agent_for(db, "D01")
    proposal = call(ctx, "propose_refund", "p-1", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    assert proposal["outcome"] == "eligible"
    refused = handoff(ctx, "shop_decided")
    assert refused["refused"] == "handoff_reason"
    # No offer of a person after a refusal (policy section exceptions); a clear request for one is still honoured.
    assert "offer a person" not in refused["explanation"]
    assert "without offering a person" in refused["explanation"]
    assert "customer_asked only when the customer clearly asks" in refused["explanation"]
    assert control(ctx) == [("agent",)]
    status = f"SELECT status FROM proposals WHERE id = '{proposal['proposal_id']}'"
    assert rows(ctx.engine, status) == [("awaiting_customer_confirmation",)]


def test_a_return_dispute_needs_named_units_the_records_do_not_show_received(db):
    ctx = agent_for(db, "D22")  # h12-o1: the duvet set has not arrived back
    assert handoff(ctx, "return_disputed", "h12-o1", units=["h12-o1-u1"])["ok"] is True


def test_a_return_dispute_is_about_the_named_units_not_others_of_the_order(db):
    ctx = agent_for(db, "D02")  # the bowl and the plate arrived back; the napkins did not
    bowl, napkins = "d02-o1-u1", "d02-o1-u3"
    refused = handoff(ctx, "return_disputed", "d02-o1", units=[bowl])
    assert refused["refused"] == "handoff_reason"
    assert f"the records show {bowl} received back or already refunded" in refused["explanation"]
    assert "A unit received back is requested with propose_refund" in refused["explanation"]
    assert handoff(ctx, "return_disputed", "d02-o1", "hand-2", units=[napkins, bowl])["refused"] == "handoff_reason"
    assert handoff(ctx, "return_disputed", "d02-o1", "hand-3", units=[napkins])["ok"] is True


def test_a_return_dispute_names_the_customers_order_and_its_units(db):
    ctx = agent_for(db, "D01")  # d01-o1: the mug arrived back
    assert handoff(ctx, "return_disputed", "d01-o1", units=["d01-o1-u1"])["refused"] == "handoff_reason"
    assert "name the customer's order" in handoff(ctx, "return_disputed", "", "hand-2")["explanation"]
    for units in ([], ["d01-o1-u9"], ["d02-o1-u3"]):  # none, unknown, or not of this order
        refused = handoff(ctx, "return_disputed", "d01-o1", "hand-3", units=units)
        assert "name the units of that order the customer says were sent" in refused["explanation"]


def test_a_dispute_names_an_order_of_the_signed_in_customer(db):
    ctx = agent_for(db, "D07")  # d07-o2 is Hugo's
    assert "name the customer's order" in handoff(ctx, "delivery_disputed", "d07-o2")["explanation"]


def test_what_only_the_conversation_shows_stays_the_agents_claim(db):
    ctx = agent_for(db, "D01")
    assert handoff(ctx, "shipping_refund")["ok"] is True
    assert rows(ctx.engine, "SELECT origin FROM handoffs") == [("agent",)]


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
