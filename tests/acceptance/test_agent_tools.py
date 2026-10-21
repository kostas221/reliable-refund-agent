"""The agent's tools on a real PostgreSQL: what the model can see and ask for, and what the database holds after.

Each call goes through call_tool, as the conversation graph will call it, with JSON arguments and a tool call ID.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from refund_agent.agent.tools import UNTRUSTED, ToolContext, call_tool
from refund_agent.fixtures import seed
from refund_agent.refunds import Actor, cancel, confirm, decide, open_conversation
from tests.acceptance.flows import DEVELOPMENT, POLICY, SCENARIOS, policy_of, proposed, rows


def agent_for(db, scenario_id, configuration="A"):
    """The tools of a new conversation of the scenario's customer."""
    scenario = DEVELOPMENT[scenario_id]
    seed(db("owner"), scenario, POLICY)
    app = db("app")
    customer = scenario.customer.id
    conversation = open_conversation(app, Actor("customer", customer), scenario.now)
    return ToolContext(app, POLICY, lambda: scenario.now, customer, conversation, configuration)


def said(ctx, words, author="customer"):
    """A message of the conversation, stored as the conversation graph stores it before the turn's tools run."""
    with ctx.engine.begin() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM messages WHERE conversation_id = :c"), {"c": ctx.conversation_id}
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO messages (id, conversation_id, author, content_untrusted, created_at) "
                "VALUES (:id, :c, :author, :words, :at)"
            ),
            {
                "id": f"{ctx.conversation_id}/m{count:04d}",
                "c": ctx.conversation_id,
                "author": author,
                "words": words,
                "at": ctx.clock(),
            },
        )


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
        return ToolContext(app, policy, lambda: scenario.now, customer, conversation)

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
    # The agent cannot name a request to pay (v1.1 step 2): the argument is refused, and the backend finds only this
    # conversation's requests, of which there are none.
    named = call(ctx, "execute_refund", proposal_id=hugos.id)
    assert (named["ok"], named["error"]) == (False, "invalid_arguments")
    assert call(ctx, "execute_refund", "call-2")["refused"] == "invalid_transition"
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
    assert result["policy_citations"] == ["refund-policy/v2/amount"]  # the amount is what was paid
    assert result["next_step"].startswith("The proposal is now on the customer's card")  # what now exists


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
    early = call(ctx, "execute_refund", "call-2")
    assert (early["ok"], early["refused"]) == (False, "status_approved")
    assert "confirm" in early["explanation"] and "approve" in early["explanation"]
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(0,)]

    approve(ctx, proposal, staff="d01-rui")
    paid = call(ctx, "execute_refund", "call-3")["receipt"]
    assert paid["amount_minor"] == 4990
    assert call(ctx, "execute_refund", "call-3")["receipt"] == paid  # the step ran again
    assert call(ctx, "execute_refund", "call-4")["receipt"] == paid  # a new call, same refund
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(1,)]
    assert call(ctx, "get_request_status", proposal_id=proposal)["request"]["receipt"] == paid


def test_configuration_c_reaches_execute_only_through_the_context(db):
    lab = agent_for(db, "D01", configuration="C")
    proposal = call(lab, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])["proposal_id"]
    assert call(lab, "execute_refund")["ok"] is True  # the lab paid without any approval
    assert rows(lab.engine, "SELECT count(*) FROM refund_operations") == [(1,)]
    assert rows(lab.engine, "SELECT proposal_id FROM refund_operations") == [(proposal,)]


def test_execute_pays_the_conversations_latest_request_that_the_policy_did_not_refuse(db):
    ctx = agent_for(db, "D02")  # the bowl and the plate arrived back; the napkins did not
    nothing = call(ctx, "execute_refund")
    assert (nothing["refused"], nothing["explanation"]) == (
        "invalid_transition",
        "this conversation has no refund request to pay",
    )
    assert rows(ctx.engine, "SELECT outcome, reason FROM audit_events WHERE event = 'execute'") == [
        ("rejected", "invalid_transition")
    ]
    call(ctx, "propose_refund", "p-1", order_id="d02-o1", unit_ids=["d02-o1-u1"])
    both = call(ctx, "propose_refund", "p-2", order_id="d02-o1", unit_ids=["d02-o1-u1", "d02-o1-u2"])["proposal_id"]
    approve(ctx, both, staff="d02-rui")
    refused = call(ctx, "propose_refund", "p-3", order_id="d02-o1", unit_ids=["d02-o1-u3"])
    assert refused["outcome"] == "refused"  # the napkins: a later proposal, but not one to pay
    assert call(ctx, "execute_refund", "x-1")["receipt"]["amount_minor"] == 10480
    assert rows(ctx.engine, "SELECT proposal_id FROM refund_operations") == [(both,)]


# Handoff


def test_after_a_handoff_the_agent_changes_nothing(db):
    ctx = agent_for(db, "D05")
    said(ctx, "That is not fair. I want to talk to a person.")
    result = call(
        ctx,
        "request_handoff",
        reason="The customer wants a person to review the late request.",
        reason_code="customer_asked",
        customer_words="I want to talk to a person",
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


# The customer's request for a person rests on words the customer wrote (v1.1 step 2)


def asked(ctx, words, call_id="hand-1"):
    return call(
        ctx,
        "request_handoff",
        call_id,
        reason_code="customer_asked",
        customer_words=words,
        reason="A test of the handoff check.",
        customer_goal="",
        confirmed_facts="",
        decision_needed="",
    )


def test_a_request_for_a_person_needs_words_the_customer_wrote(db):
    ctx = agent_for(db, "D15")
    said(ctx, "Hi, my game controller has not arrived yet. Where is it?")
    said(ctx, "Would you like me to connect you with a staff member?", author="agent")
    for words, unmet in (
        ("", "customer_words must give the customer's own words that ask for a person"),
        ("I want to talk to a person", "customer_words are not words the customer wrote in this conversation"),
        ("connect you with a staff member", "customer_words are not words the customer wrote in this conversation"),
    ):
        refused = asked(ctx, words)
        assert (refused["refused"], refused["explanation"].split(".")[0]) == ("handoff_reason", unmet)
    assert control(ctx) == [("agent",)]
    said(ctx, "Yes, please do.")  # a yes to the offer is a request for a person
    assert asked(ctx, "\u201cyes, please do\u201d", "hand-2")["ok"] is True  # case and quotation marks aside
    yes = f"{ctx.conversation_id}/m0002"  # the third message: the request rests on this one
    assert rows(ctx.engine, "SELECT origin, reason FROM handoffs") == [
        (
            "customer",
            f'customer_asked: A test of the handoff check. The customer wrote: "\u201cyes, please do\u201d" '
            f"(message {yes}).",
        )
    ]


# The assessment: the decision a proposal would get, with its facts, and nothing written (v1.1 step 2)


def counts(engine):
    tables = ("proposals", "proposal_units", "audit_events", "refund_operations", "ledger_lines", "handoffs")
    return {table: rows(engine, f"SELECT count(*) FROM {table}")[0][0] for table in tables}


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_an_assessment_writes_nothing_and_agrees_with_the_proposal(db, scenario_id):
    scenario = SCENARIOS[scenario_id]
    policy = policy_of(scenario)
    seed(db("owner"), scenario, policy)
    app = db("app")
    customer = scenario.customer.id
    conversation = open_conversation(app, Actor("customer", customer), scenario.now)
    ctx = ToolContext(app, policy, lambda: scenario.now, customer, conversation)
    for order in (o for o in scenario.fixture.orders if o.customer == customer):
        units = [unit.id for unit in order.units]
        for n, selection in enumerate([[unit] for unit in units] + ([units] if len(units) > 1 else [])):
            before = counts(app)
            found = call(ctx, "assess_refund", f"a-{order.id}-{n}", order_id=order.id, unit_ids=selection)
            assert counts(app) == before, selection
            made = call(ctx, "propose_refund", f"p-{order.id}-{n}", order_id=order.id, unit_ids=selection)
            assert (found["outcome"], found["policy_citations"], found["amount_minor"]) == (
                made["outcome"],
                made["policy_citations"],
                made["amount_minor"],
            ), selection


def test_an_assessment_of_a_late_request_gives_its_deadline(db):
    late = call(agent_for(db, "D05"), "assess_refund", order_id="d05-o1", unit_ids=["d05-o1-u1"])
    assert (late["outcome"], late["policy_citations"]) == ("refused", ["refund-policy/v2/window"])
    assert late["order"]["refund_deadline"] == "2026-08-24T10:00:00+00:00"  # delivered 25 July, plus 30 days


def test_an_assessment_of_units_already_refunded_gives_their_receipt(db):
    paid = call(agent_for(db, "D20"), "assess_refund", order_id="h10-o1", unit_ids=["h10-o1-u1", "h10-o1-u2"])
    assert paid["policy_citations"] == ["refund-policy/v2/remaining"]
    assert {(u["refunded"], u["receipt_number"]) for u in paid["units"]} == {(True, "R-H10-0001")}


def test_an_assessment_shows_the_earlier_on_time_proposal_that_sends_a_late_request_to_a_person(db):
    expired = call(agent_for(db, "D10"), "assess_refund", order_id="d10-o1", unit_ids=["d10-o1-u1"])
    assert (expired["outcome"], expired["units"][0]["earlier_on_time_proposal"]) == ("needs_person", True)


def test_an_assessment_of_an_order_with_two_payments_shows_them(db):
    split = call(agent_for(db, "D29"), "assess_refund", order_id="h19-o1", unit_ids=["h19-o1-u1"])
    assert (split["outcome"], split["order"]["payment_records"], split["order"]["one_valid_payment"]) == (
        "needs_person",
        2,
        False,
    )


def test_an_eligible_assessment_gives_the_amount_and_reserves_nothing(db):
    eligible = call(agent_for(db, "D01"), "assess_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    assert (eligible["outcome"], eligible["amount_minor"], eligible["units"][0]["received_back"]) == (
        "eligible",
        4990,
        True,
    )
    assert eligible["policy_citations"] == ["refund-policy/v2/amount"]
    # Scoped to its own effect: an assessment cannot tell whether a proposal already exists (D17 of step 2).
    assert eligible["next_step"].startswith("This assessment does not create or change a proposal.")


def test_an_assessment_of_another_customers_order_or_a_wrong_unit_is_refused_and_writes_nothing(db):
    ctx = agent_for(db, "D07")  # d07-o2 is Hugo's
    before = counts(ctx.engine)
    assert call(ctx, "assess_refund", order_id="d07-o2", unit_ids=["d07-o2-u1"])["refused"] == "actor_owns"
    assert call(ctx, "assess_refund", order_id="d07-o1", unit_ids=["d07-o2-u1"])["refused"] == "valid_values"
    repeated = call(ctx, "assess_refund", order_id="d07-o1", unit_ids=["d07-o1-u1", "d07-o1-u1"])
    assert repeated["refused"] == "valid_values"
    assert counts(ctx.engine) == before


# Paying the conversation's request: reach, replay, cancellation and handoff (review of 2026-10-21)


def test_the_lab_still_reaches_a_request_the_policy_refused_and_a_still_does_not(db):
    lab = agent_for(db, "D05", configuration="C")  # a late request: the policy refuses it
    refused = call(lab, "propose_refund", order_id="d05-o1", unit_ids=["d05-o1-u1"])["proposal_id"]
    assert call(lab, "execute_refund")["ok"] is True  # without the lab-disabled checks, a refused request is paid
    assert rows(lab.engine, "SELECT proposal_id FROM refund_operations") == [(refused,)]


def test_configuration_a_finds_no_request_to_pay_when_the_policy_refused_it(db):
    ctx = agent_for(db, "D05")
    call(ctx, "propose_refund", order_id="d05-o1", unit_ids=["d05-o1-u1"])
    assert call(ctx, "execute_refund")["refused"] == "invalid_transition"
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(0,)]


def test_a_call_that_paid_returns_its_own_receipt_and_never_pays_a_later_request(db):
    ctx = agent_for(db, "D02")
    bowl = call(ctx, "propose_refund", "p-1", order_id="d02-o1", unit_ids=["d02-o1-u1"])["proposal_id"]
    approve(ctx, bowl, staff="d02-rui")
    paid = call(ctx, "execute_refund", "x-1")["receipt"]
    plate = call(ctx, "propose_refund", "p-2", order_id="d02-o1", unit_ids=["d02-o1-u2"])["proposal_id"]
    approve(ctx, plate, staff="d02-rui")
    assert call(ctx, "execute_refund", "x-1")["receipt"] == paid  # the same call again, after a restart
    assert rows(ctx.engine, "SELECT proposal_id FROM refund_operations") == [(bowl,)]
    assert call(ctx, "execute_refund", "x-2")["receipt"]["amount_minor"] == 3490  # a new call pays the plate
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(2,)]


def test_a_cancelled_request_is_not_paid(db):
    ctx = agent_for(db, "D01")
    proposal = call(ctx, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])["proposal_id"]
    customer = Actor("customer", ctx.customer_id)
    confirm(ctx.engine, customer, proposal, "confirmed", ctx.clock(), POLICY)
    assert cancel(ctx.engine, customer, proposal, ctx.clock(), POLICY) == "cancelled"  # the cancel button
    assert call(ctx, "execute_refund")["ok"] is False
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(0,)]


def test_an_approved_request_is_not_paid_after_a_handoff(db):
    ctx = agent_for(db, "D01")
    proposal = call(ctx, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])["proposal_id"]
    approve(ctx, proposal, staff="d01-rui")
    said(ctx, "I would like to talk to a person, please.")
    assert asked(ctx, "talk to a person")["ok"] is True
    assert call(ctx, "execute_refund")["refused"] == "agent_in_control"
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(0,)]


# Received back as the policy counts it, in every read (review of 2026-10-21)


@pytest.mark.parametrize(("hours", "received"), [(-1, True), (0, True), (1, False)])
def test_a_unit_is_received_back_in_the_order_list_only_once_its_time_has_come(db, hours, received):
    ctx = agent_for(db, "D01")
    with db("owner").begin() as conn:  # the return recorded this many hours from now
        conn.execute(
            text("UPDATE order_units SET received_back_at = :at WHERE id = 'd01-o1-u1'"),
            {"at": ctx.clock() + timedelta(hours=hours)},
        )
    (unit,) = call(ctx, "list_my_orders")["orders"][0]["units"]
    assessed = call(ctx, "assess_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    assert (unit["received_back"], assessed["units"][0]["received_back"]) == (received, received)
    assert assessed["outcome"] == ("eligible" if received else "refused")


def test_an_assessment_and_a_proposal_agree_on_a_unit_with_nothing_paid(db):
    ctx = agent_for(db, "D01")
    with db("owner").begin() as conn:
        conn.execute(text("UPDATE order_units SET paid_minor = 0 WHERE id = 'd01-o1-u1'"))
    found = call(ctx, "assess_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    made = call(ctx, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    assert (
        (found["outcome"], found["policy_citations"], found["amount_minor"])
        == (
            made["outcome"],
            made["policy_citations"],
            made["amount_minor"],
        )
        == ("refused", ["refund-policy/v2/amount"], None)
    )


# What the tools tell the agent after a refusal and a payment (repairs of step 2, plan change log 2026-10-22)


@pytest.mark.parametrize("tool", ["assess_refund", "propose_refund"])
def test_a_refusal_for_a_missing_return_names_the_case_for_a_person(db, tool):
    # D22 of step 2: "Propose nothing" was followed where the policy names a case for a person.
    ctx = agent_for(db, "D22")  # h12-o1: the duvet set has not arrived back
    refused = call(ctx, tool, order_id="h12-o1", unit_ids=["h12-o1-u1"])
    assert refused["outcome"] == "refused"
    assert "already sent, the policy names that case for a person" in refused["next_step"]
    assert "reason_code return_disputed" in refused["next_step"]
    assert "If they will send them later, explain that they must arrive first." in refused["next_step"]


@pytest.mark.parametrize("tool", ["assess_refund", "propose_refund"])
def test_a_refusal_for_lateness_names_no_case_for_a_person(db, tool):
    ctx = agent_for(db, "D05")  # a late request: an exception is refused, not handed off
    refused = call(ctx, tool, order_id="d05-o1", unit_ids=["d05-o1-u1"])
    assert refused["outcome"] == "refused"
    assert "for a person" not in refused["next_step"] and "return_disputed" not in refused["next_step"]


def test_a_paid_refund_is_told_against_the_original_payment_and_the_ledger_only_when_asked(db):
    ctx = agent_for(db, "D01")
    proposal = call(ctx, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])["proposal_id"]
    approve(ctx, proposal, staff="d01-rui")
    paid = call(ctx, "execute_refund", "x-1")
    assert paid["next_step"].startswith("The refund is paid and recorded against the order's original payment.")
    assert "only if the customer asks when or how the money arrives" in paid["next_step"]
    assert paid["receipt"]["payment_id"] == "d01-o1-p1"  # the original payment the words refer to
