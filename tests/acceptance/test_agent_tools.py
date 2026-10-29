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
from refund_agent.refunds import Actor, Refused, cancel, confirm, decide, open_conversation, refer_to_staff
from refund_agent.scenarios import PastProposal
from tests.acceptance.flows import DEVELOPMENT, POLICY, SCENARIOS, policy_of, proposed, rows


def agent_for(db, scenario_id, configuration="A"):
    """The tools of a new conversation of the scenario's customer."""
    scenario = DEVELOPMENT[scenario_id]
    seed(db("owner"), scenario, POLICY)
    app = db("app")
    customer = scenario.customer.id
    conversation = open_conversation(app, Actor("customer", customer), scenario.now)
    return ToolContext(app, POLICY, lambda: scenario.now, customer, conversation, configuration)


def said(ctx, words, author="customer", fact_line=False):
    """A message of the conversation, stored as the conversation graph stores it before the turn's tools run; a fact
    line is the agent's, marked as said from the records (refund_agent/agent/facts.py)."""
    with ctx.engine.begin() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM messages WHERE conversation_id = :c"), {"c": ctx.conversation_id}
        ).scalar_one()
        row = {
            "id": f"{ctx.conversation_id}/m{count:04d}",
            "c": ctx.conversation_id,
            "author": author,
            "words": words,
            "at": ctx.clock(),
        }
        if fact_line:
            conn.execute(
                text(
                    "INSERT INTO messages (id, conversation_id, author, content_untrusted, created_at, fact_line) "
                    "VALUES (:id, :c, :author, :words, :at, true)"
                ),
                row,
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO messages (id, conversation_id, author, content_untrusted, created_at) "
                    "VALUES (:id, :c, :author, :words, :at)"
                ),
                row,
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
    refusal, never an error. With no customer message, a unit among look-alikes is refused for want of the
    customer's words (units_named)."""
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
            if own:
                assert answer["ok"] or answer["refused"] == "units_named", answer
            else:
                assert answer.get("refused") == "actor_owns", answer


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


def test_a_paid_request_carries_the_section_that_explains_its_units_are_settled(db):
    # D20, tries 1 and 2 of 2026-10-23: the agent gave the receipt and left out (refund-policy/v2/remaining), which
    # the instructions already ask for; the citation now sits beside the receipt the agent reads (review after the
    # selection check). A request not paid has none.
    (paid,) = call(agent_for(db, "D20"), "list_my_orders")["orders"][0]["requests"]
    assert (paid["receipt_number"], paid["policy_citation"]) == ("R-H10-0001", "refund-policy/v2/remaining")


def test_a_request_not_paid_carries_no_such_section(db):
    (expired,) = call(agent_for(db, "D10"), "get_my_order", order_id="d10-o1")["order"]["requests"]
    assert "policy_citation" not in expired


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
    assert "name its order and units in the handoff" in refused["explanation"]
    assert call(late, "propose_refund", "p-4", order_id="d02-o1", unit_ids=[bowl])["outcome"] == "needs_person"
    with db("owner").begin() as conn:  # for example, a corrected return record
        conn.execute(text("UPDATE orders SET material_version = material_version + 1 WHERE id = 'd02-o1'"))
    assert handoff(late, "shop_decided", call_id="hand-2")["refused"] == "handoff_reason"  # decided on the old order
    assert call(late, "propose_refund", "p-5", order_id="d02-o1", unit_ids=[bowl])["outcome"] == "needs_person"
    assert handoff(late, "shop_decided", call_id="hand-3")["ok"] is True


# A case for staff named in the handoff itself (final evaluation of v1.1, H77): the agent knew that a staff member
# decides an order with no delivery time and handed off with its order and unit before any proposal; the handoff was
# refused for want of one, and the agent explained instead of proposing. The backend now decides the named units.


def proposals_of(ctx):
    """This conversation's proposals; a fixture's past ones (D10's expired one) belong to none."""
    return rows(
        ctx.engine,
        "SELECT status, status_reason, order_id FROM proposals "
        f"WHERE conversation_id = '{ctx.conversation_id}' ORDER BY created_at, id",
    )


def events_of(ctx):
    return rows(
        ctx.engine,
        "SELECT event, outcome, reason FROM audit_events WHERE event IN ('propose', 'hand_off') ORDER BY id",
    )


def test_a_handoff_that_names_a_case_for_staff_records_the_request_and_hands_off(db):
    ctx = agent_for(db, "D10")
    answer = handoff(ctx, "shop_decided", "d10-o1", units=["d10-o1-u1"])
    assert answer["ok"] is True
    assert proposals_of(ctx) == [("ineligible", "needs_person", "d10-o1")]  # the staff member sees what was asked
    units = (
        "SELECT u.order_unit_id FROM proposal_units u JOIN proposals p ON p.id = u.proposal_id "
        f"WHERE p.conversation_id = '{ctx.conversation_id}'"
    )
    assert rows(ctx.engine, units) == [("d10-o1-u1",)]
    assert control(ctx) == [("human_controlled",)]
    # Recorded as propose_refund records it, before the handoff: the same events as the two steps.
    assert events_of(ctx) == [("propose", "committed", None), ("hand_off", "committed", None)]


def test_a_handoff_for_units_the_policy_allows_is_refused_and_writes_nothing(db):
    ctx = agent_for(db, "D01")
    refused = handoff(ctx, "shop_decided", "d01-o1", units=["d01-o1-u1"])
    assert refused["refused"] == "handoff_reason"
    assert "call propose_refund with them" in refused["explanation"]
    assert proposals_of(ctx) == []  # a handoff never leaves a proposal waiting for the customer's button
    assert control(ctx) == [("agent",)]
    assert events_of(ctx) == [("hand_off", "rejected", "handoff_reason")]


def test_a_handoff_for_units_the_policy_refuses_is_refused_with_the_reason(db):
    late = replace(agent_for(db, "D02"), clock=lambda: datetime(2026, 10, 9, 12, 0, tzinfo=UTC))  # past the deadline
    refused = handoff(late, "shop_decided", "d02-o1", units=["d02-o1-u2"])
    assert refused["refused"] == "handoff_reason"
    assert "(refund-policy/v2/window)" in refused["explanation"]
    assert "without offering a person" in refused["explanation"]
    assert proposals_of(late) == []
    assert control(late) == [("agent",)]


def test_a_handoff_for_an_order_on_its_way_is_refused_with_its_status_and_the_offer_the_policy_makes(db):
    # D19 of 2026-10-21, try 3, named the order on its way in a shop_decided handoff. The policy refuses its refund
    # and offers a staff member for cancelling it (section eligible-orders), so the refusal must not forbid that offer.
    ctx = agent_for(db, "D19")
    refused = handoff(ctx, "shop_decided", "h09-o1", units=["h09-o1-u1"])
    assert refused["refused"] == "handoff_reason"
    assert "offer a person for that (refund-policy/v2/eligible-orders)" in refused["explanation"]
    assert "without offering a person" not in refused["explanation"]
    assert proposals_of(ctx) == []


def test_a_handoff_after_the_two_steps_records_the_request_once(db):
    ctx = agent_for(db, "D10")
    assert call(ctx, "propose_refund", "p-1", order_id="d10-o1", unit_ids=["d10-o1-u1"])["outcome"] == "needs_person"
    assert handoff(ctx, "shop_decided", "d10-o1", units=["d10-o1-u1"])["ok"] is True
    assert proposals_of(ctx) == [("ineligible", "needs_person", "d10-o1")]


def test_an_earlier_referral_is_decided_again_for_other_units_or_a_changed_order(db):
    ctx = agent_for(db, "D02")  # delivered 8 September 12:00, so the deadline is 8 October 12:00
    bowl, plate = "d02-o1-u1", "d02-o1-u2"
    assert call(ctx, "propose_refund", "p-1", order_id="d02-o1", unit_ids=[bowl])["outcome"] == "eligible"
    late = replace(ctx, clock=lambda: datetime(2026, 10, 9, 12, 0, tzinfo=UTC))  # the bowl's proposal lapsed
    assert call(late, "propose_refund", "p-2", order_id="d02-o1", unit_ids=[bowl])["outcome"] == "needs_person"
    # The bowl's referral does not stand for the plate, which has no request made in time.
    assert handoff(late, "shop_decided", "d02-o1", units=[plate])["refused"] == "handoff_reason"
    with db("owner").begin() as conn:  # for example, a corrected return record
        conn.execute(text("UPDATE orders SET material_version = material_version + 1 WHERE id = 'd02-o1'"))
    # Decided on the old order, so decided again, and recorded again, before the handoff.
    assert handoff(late, "shop_decided", "d02-o1", "hand-2", units=[bowl])["ok"] is True
    assert proposals_of(late)[-2:] == [("ineligible", "needs_person", "d02-o1")] * 2


def test_a_referral_is_never_returned_to_another_customer(db):
    ctx = agent_for(db, "D10")
    assert call(ctx, "propose_refund", "p-1", order_id="d10-o1", unit_ids=["d10-o1-u1"])["outcome"] == "needs_person"
    with pytest.raises(Refused) as refused:
        refer_to_staff(
            ctx.engine,
            Actor("agent", "d10-rui"),
            ctx.conversation_id,
            "d10-o1",
            ["d10-o1-u1"],
            "k",
            ctx.clock(),
            POLICY,
        )
    assert refused.value.check == "actor_owns"


def test_a_handoff_made_again_with_its_call_id_returns_the_same_handoff(db):
    ctx = agent_for(db, "D10")
    first = handoff(ctx, "shop_decided", "d10-o1", units=["d10-o1-u1"])
    again = handoff(ctx, "shop_decided", "d10-o1", units=["d10-o1-u1"])  # a resumed run makes the same call again
    assert again["ok"] is True and again["handoff_id"] == first["handoff_id"]
    assert len(proposals_of(ctx)) == 1


def test_a_handoff_for_staff_names_the_customers_order_and_its_units(db):
    ctx = agent_for(db, "D07")  # d07-o2 is another customer's order
    assert handoff(ctx, "shop_decided", "d07-o2", units=["d07-o2-u1"])["refused"] == "actor_owns"
    named = handoff(ctx, "shop_decided", "", "hand-2", units=["d07-o1-u1"])
    assert named["refused"] == "handoff_reason"
    assert "name the customer's order and the units of the request" in named["explanation"]
    assert proposals_of(ctx) == []
    assert [event for event, _, _ in events_of(ctx)] == ["hand_off", "hand_off"]  # recorded as the handoff's


# A handoff's result gives the section it rests on, as a refusal's does (final evaluation of v1.1: all 98 required
# refusal citations were shown, and 11 of 18 required handoff citations were missed).


@pytest.mark.parametrize(
    ("scenario_id", "code", "order_id", "units", "section"),
    [
        ("D10", "shop_decided", "d10-o1", ["d10-o1-u1"], "window"),  # the decision's own reasons
        ("D22", "return_disputed", "h12-o1", ["h12-o1-u1"], "return"),
        ("D15", "delivery_disputed", "h05-o1", [], "eligible-orders"),
    ],
)
def test_a_handoff_result_gives_the_section_it_rests_on(db, scenario_id, code, order_id, units, section):
    answer = handoff(agent_for(db, scenario_id), code, order_id, units=units)
    citation = f"refund-policy/v2/{section}"
    assert (answer["reason_code"], answer["policy_citations"]) == (code, [citation])
    assert f"and why, citing ({citation})" in answer["next_step"]


def test_a_handoff_the_customer_asked_for_rests_on_the_exceptions_section(db):
    ctx = agent_for(db, "D36")
    said(ctx, "I'd like to talk to someone from your team about it, please.")
    answer = call(
        ctx,
        "request_handoff",
        reason_code="customer_asked",
        customer_words="I'd like to talk to someone from your team about it",
        reason="The customer asks for a person.",
        customer_goal="",
        confirmed_facts="",
        decision_needed="",
    )
    assert answer["policy_citations"] == ["refund-policy/v2/exceptions"]


# The sections an eligible proposal's circumstances rest on (final evaluation of v1.1, 2026-10-26): its result gave only
# the amount section, and the scenarios' authors required window (H26, 6 hours before the deadline: 9 misses), validity
# (H74, an earlier request invalidated by an order correction: 10) and approval (H30 and H50, an earlier request
# cancelled or rejected: 6). A refusal's result gives its sections, and all 98 required refusal citations were shown.

WINDOW, VALIDITY, APPROVAL, AMOUNT = (f"refund-policy/v2/{s}" for s in ("window", "validity", "approval", "amount"))


def proposed_at(ctx, when, call_id="p-1", units=("d01-o1-u1",), order_id="d01-o1"):
    at = replace(ctx, clock=lambda: when)
    return call(at, "propose_refund", call_id, order_id=order_id, unit_ids=list(units))


def test_a_first_proposal_far_from_the_deadline_cites_only_its_amount(db):
    answer = call(agent_for(db, "D01"), "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    assert answer["policy_citations"] == [AMOUNT]
    assert "Tell the customer also" not in answer["next_step"]


def test_a_proposal_made_close_to_the_deadline_says_it_is_on_time(db):
    ctx = agent_for(db, "D01")  # delivered 6 September 16:00, so the 30-day limit ends 6 October 16:00
    # Made exactly 72 hours before the deadline, the proposal expires at the deadline: the limit never passes while it
    # is open. A minute later it would.
    assert proposed_at(ctx, datetime(2026, 10, 3, 16, 0, tzinfo=UTC))["policy_citations"] == [AMOUNT]
    answer = proposed_at(ctx, datetime(2026, 10, 3, 16, 1, tzinfo=UTC), "p-2")
    assert answer["policy_citations"] == [AMOUNT, WINDOW]
    assert "ends at 2026-10-06 16:00 UTC" in answer["next_step"] and f"({WINDOW})" in answer["next_step"]


def test_a_proposal_after_an_earlier_one_lapsed_says_why_a_new_one_was_needed(db):
    ctx = agent_for(db, "D01")
    first = call(ctx, "propose_refund", "p-1", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    answer = proposed_at(ctx, ctx.clock() + timedelta(hours=73), "p-2")  # the first one expired, unpaid
    assert answer["policy_citations"] == [AMOUNT, VALIDITY]
    assert f"{first['proposal_id']}" in answer["next_step"] and "expired" in answer["next_step"]
    with db("owner").begin() as conn:  # the order record is corrected: the open proposal stops being valid
        conn.execute(text("UPDATE orders SET material_version = material_version + 1 WHERE id = 'd01-o1'"))
    again = proposed_at(ctx, ctx.clock() + timedelta(hours=74), "p-3")
    assert again["policy_citations"] == [AMOUNT, VALIDITY]
    assert "stopped being valid" in again["next_step"]


def test_a_proposal_after_an_earlier_one_was_declined_or_rejected_needs_both_decisions_again(db):
    ctx = agent_for(db, "D01")
    first = call(ctx, "propose_refund", "p-1", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    confirm(ctx.engine, Actor("customer", ctx.customer_id), first["proposal_id"], "declined", ctx.clock(), POLICY)
    answer = call(ctx, "propose_refund", "p-2", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    assert answer["policy_citations"] == [AMOUNT, APPROVAL]
    assert "cancelled" in answer["next_step"] and f"({APPROVAL})" in answer["next_step"]
    confirm(ctx.engine, Actor("customer", ctx.customer_id), answer["proposal_id"], "confirmed", ctx.clock(), POLICY)
    decide(ctx.engine, Actor("staff", "d01-rui"), answer["proposal_id"], "rejected", ctx.clock(), POLICY, reason="No")
    again = call(ctx, "propose_refund", "p-3", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    assert again["policy_citations"] == [AMOUNT, APPROVAL]
    assert "rejected by a staff member" in again["next_step"]


def test_a_proposal_replaced_by_the_customers_change_counts_for_neither(db):
    ctx = agent_for(db, "D02")  # the bowl, then the bowl and the plate: the first is superseded
    call(ctx, "propose_refund", "p-1", order_id="d02-o1", unit_ids=["d02-o1-u1"])
    answer = call(ctx, "propose_refund", "p-2", order_id="d02-o1", unit_ids=["d02-o1-u1", "d02-o1-u2"])
    assert answer["policy_citations"] == [AMOUNT]


def test_an_earlier_request_names_only_the_items_it_was_for(db):
    # Review of 2026-10-27: an earlier request for the bowl alone is not one "for these items" when the new proposal
    # adds the plate. The fact names what the records show, and an earlier request for other items counts for nothing.
    ctx = agent_for(db, "D02")
    customer = Actor("customer", ctx.customer_id)
    plate = call(ctx, "propose_refund", "p-1", order_id="d02-o1", unit_ids=["d02-o1-u2"])
    confirm(ctx.engine, customer, plate["proposal_id"], "declined", ctx.clock(), POLICY)
    bowl = call(ctx, "propose_refund", "p-2", order_id="d02-o1", unit_ids=["d02-o1-u1"])
    assert bowl["policy_citations"] == [AMOUNT]  # the declined plate is another item
    confirm(ctx.engine, customer, bowl["proposal_id"], "declined", ctx.clock(), POLICY)
    both = call(ctx, "propose_refund", "p-3", order_id="d02-o1", unit_ids=["d02-o1-u1", "d02-o1-u2"])
    assert both["policy_citations"] == [AMOUNT, APPROVAL]
    said = both["next_step"].lower()  # the step's first fact starts with a capital
    assert f"an earlier request for the stoneware dinner plate ended unpaid ({plate['proposal_id']} was cancelled)" in (
        said
    )
    assert f"an earlier request for the glass salad bowl ended unpaid ({bowl['proposal_id']} was cancelled)" in said
    assert said.index("dinner plate") < said.index("salad bowl")  # in the order they were made
    assert "these items" not in said


@pytest.mark.parametrize(
    ("status", "section"), [("rejected", APPROVAL), ("cancelled", APPROVAL), ("invalidated", VALIDITY)]
)
def test_an_earlier_request_in_the_shops_history_counts_too(db, status, section):
    # H30, H50 and H74: the earlier request was made in another conversation, before this one.
    scenario = DEVELOPMENT["D01"]
    past = PastProposal(
        id="d01-p9", units=("d01-o1-u1",), created_at=datetime(2026, 9, 18, 10, tzinfo=UTC), status=status
    )
    fixture = scenario.fixture.model_copy(update={"past_proposals": (past,)})
    seed(db("owner"), scenario.model_copy(update={"fixture": fixture}), POLICY)
    app = db("app")
    conversation = open_conversation(app, Actor("customer", "d01-ana"), scenario.now)
    ctx = ToolContext(app, POLICY, lambda: scenario.now, "d01-ana", conversation)
    answer = call(ctx, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])
    assert answer["policy_citations"] == [AMOUNT, section]
    assert "d01-p9" in answer["next_step"]


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


# A request to refund shipping rests on the customer's words (review after the selection check, 2026-10-23)


def shipping(ctx, words, call_id="hand-1"):
    return call(
        ctx,
        "request_handoff",
        call_id,
        reason_code="shipping_refund",
        customer_words=words,
        reason="A test of the handoff check.",
        customer_goal="",
        confirmed_facts="",
        decision_needed="",
    )


def test_a_question_about_shipping_is_answered_and_the_refund_goes_on(db):
    # D39, all three tries of Luna none on 2026-10-23: the agent quoted the question "Will the shipping I paid be
    # refunded too, or just the kettle?" as a request, the check took it, and the kettle was never refunded.
    ctx = agent_for(db, "D39")
    question = "Hi, I returned the glass kettle. Will the shipping I paid be refunded too, or just the kettle?"
    said(ctx, question)
    kettle = call(ctx, "propose_refund", "p-1", order_id="d39-o1", unit_ids=["d39-o1-u1"])
    assert kettle["outcome"] == "eligible"
    refused = shipping(ctx, question)
    assert refused["refused"] == "handoff_reason"
    explanation = refused["explanation"]
    assert (
        explanation.split(".")[0] == "that message is not a yes to your offer of a staff member for the shipping charge"
    )
    assert "Answer a question about shipping from (refund-policy/v2/shipping)" in explanation
    assert "Would you like a staff member to review the shipping charge?" in explanation
    assert "go on with the refund of any item the customer asked for" in explanation
    assert "customer_asked" not in explanation  # the tail for a request for a person does not apply
    # A refused attempt changes nothing: no handoff, the conversation stays the agent's, the kettle's proposal open.
    assert control(ctx) == [("agent",)]
    assert rows(ctx.engine, "SELECT count(*) FROM handoffs") == [(0,)]
    status = f"SELECT status FROM proposals WHERE id = '{kettle['proposal_id']}'"
    assert rows(ctx.engine, status) == [("awaiting_customer_confirmation",)]


def test_a_request_to_refund_shipping_is_handed_off_on_the_yes_to_the_offer(db):
    # D40: a request in clear words gets the offer first, and the customer's yes is what the handoff rests on.
    ctx = agent_for(db, "D40")
    said(
        ctx,
        "Hello, you refunded my kettle last week, thank you, but I also paid 18 reais shipping for a kettle that "
        "arrived broken. I want the shipping refunded.",
    )
    refused = shipping(ctx, "I want the shipping refunded.")
    assert refused["explanation"].startswith("that message is not a yes to your offer of a staff member")
    said(
        ctx,
        "Shipping is never refunded automatically. Would you like a staff member to review the shipping charge?",
        "agent",
    )
    said(ctx, "Yes, please.")
    assert shipping(ctx, "Yes, please.", "hand-2")["ok"] is True
    request = f"{ctx.conversation_id}/m0002"  # the staff member sees the words the request rests on
    assert rows(ctx.engine, "SELECT origin, reason FROM handoffs") == [
        (
            "agent",
            'shipping_refund: A test of the handoff check. The customer wrote: "Yes, please." '
            f"(message {request}, a yes to the agent's offer of a staff member for the shipping charge).",
        )
    ]


# What a handoff closed (review of the model comparison, 2026-10-24): in D28 the request was already cancelled by the
# customer's button, and the agent told the customer the handoff had closed it. The result now says what it closed, from
# the handoff's own record, so a second call reports the same.


def asks_for_a_person(ctx, call_id="hand-1"):
    said(ctx, "I want to talk to a person, please.")
    return call(
        ctx,
        "request_handoff",
        call_id,
        reason_code="customer_asked",
        customer_words="I want to talk to a person, please.",
        reason="A test of what a handoff closed.",
        customer_goal="",
        confirmed_facts="",
        decision_needed="",
    )


def mug_proposed(ctx):
    said(ctx, "Please refund my blue mug.")
    return call(ctx, "propose_refund", "p-1", order_id="d01-o1", unit_ids=["d01-o1-u1"])["proposal_id"]


def test_a_handoff_says_which_open_request_it_closed_and_says_it_again_when_asked_again(db):
    ctx = agent_for(db, "D01")
    proposal = mug_proposed(ctx)
    first = asks_for_a_person(ctx)
    assert first["closed_request"] == proposal
    assert f"Request {proposal}, which was not paid, is now closed" in first["next_step"]
    again = asks_for_a_person(ctx, "hand-2")  # the conversation is already handed off: the same handoff, as recorded
    assert (again["handoff_id"], again["closed_request"]) == (first["handoff_id"], proposal)


def test_a_handoff_after_a_cancellation_closed_nothing_and_says_so(db):
    ctx = agent_for(db, "D01")
    proposal = mug_proposed(ctx)
    customer = Actor("customer", ctx.customer_id)
    confirm(ctx.engine, customer, proposal, "confirmed", ctx.clock(), POLICY)
    cancel(ctx.engine, customer, proposal, ctx.clock(), POLICY)
    result = asks_for_a_person(ctx)
    assert result["closed_request"] is None
    assert result["next_step"].startswith("This handoff closed no request")
    assert rows(ctx.engine, f"SELECT status FROM proposals WHERE id = '{proposal}'") == [("cancelled",)]


def test_a_handoff_after_a_payment_closed_nothing_and_the_refund_stays_paid(db):
    ctx = agent_for(db, "D01")
    proposal = mug_proposed(ctx)
    approve(ctx, proposal, "d01-rui")
    assert call(ctx, "execute_refund", "pay-1")["ok"] is True
    result = asks_for_a_person(ctx)
    assert result["closed_request"] is None
    assert "A refund already paid stays paid." in result["next_step"]
    assert rows(ctx.engine, f"SELECT status FROM proposals WHERE id = '{proposal}'") == [("refunded",)]
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(1,)]


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
            f"(message {yes}, a yes to the agent's offer of a person).",
        )
    ]


def test_a_request_for_a_person_names_one_or_answers_an_offer_of_one(db):
    # The contrasting baseline (2026-10-22): the agent quoted "Can I cancel it?", which the customer wrote but which
    # asks for no one, and the backend accepted it (D38 try 1).
    ctx = agent_for(db, "D38")
    said(ctx, "Hello, my rice cooker order is still on its way, but I don't need it any more. Can I cancel it?")
    no_person = "that message does not ask for a person: it names none, or declines one, or answers no offer of one"
    refused = asked(ctx, "Can I cancel it?")
    assert (refused["refused"], refused["explanation"].split(".")[0]) == ("handoff_reason", no_person)
    said(ctx, "Your order is on its way, so I can't cancel it here.", author="agent")  # no offer of a person
    said(ctx, "Yes, please.")
    refused = asked(ctx, "Yes, please.", "hand-2")
    no_offer = "that message is a yes, but your message just before it offers no person in words this check can read"
    assert (refused["refused"], refused["explanation"].split(".")[0]) == ("handoff_reason", no_offer)
    assert control(ctx) == [("agent",)]
    said(ctx, "Then I'd like to talk to someone from your team.")
    assert asked(ctx, "I'd like to talk to someone from your team", "hand-3")["ok"] is True
    named = "SELECT origin, reason LIKE '%which names a person).' FROM handoffs"
    assert rows(ctx.engine, named) == [("customer", True)]


def test_a_yes_to_an_offer_the_check_cannot_read_asks_the_agent_to_offer_plainly(db):
    # D37 try 3 (2026-10-22): after a false refusal of "Yes, please." the agent told the customer to ask for a staff
    # member directly. The refusal now says to ask the offer plainly, so the customer's next yes is the request.
    ctx = agent_for(db, "D37")
    said(ctx, "Hello, my rice cooker order is still on its way, but I don't need it any more. Can I cancel it?")
    said(ctx, "Cancelling is outside this process. Someone from the team could look at it.", author="agent")
    said(ctx, "Yes, please.")
    refused = asked(ctx, "Yes, please.")
    assert refused["refused"] == "handoff_reason"
    assert "Would you like me to connect you with a staff member?" in refused["explanation"]
    assert "without offering a person" not in refused["explanation"]  # the tail for a refused request does not apply
    said(ctx, "Would you like me to connect you with a staff member?", author="agent")
    said(ctx, "Yes, please.")
    assert asked(ctx, "Yes, please.", "hand-2")["ok"] is True


# Look-alike items: a proposal waits for the customer's words that say which (plan change log, 2026-10-23)

SCARF = "Hi, I posted the linen scarf back last week. Can I have a refund?"  # D31: fits the olive and the rust scarf


def proposals(ctx):
    return rows(
        ctx.engine,
        "SELECT status, (SELECT array_agg(order_unit_id ORDER BY order_unit_id) FROM proposal_units "
        "WHERE proposal_id = p.id) FROM proposals p ORDER BY created_at, created_xact",
    )


@pytest.mark.parametrize("configuration", ["A", "C"])
def test_a_proposal_among_look_alikes_waits_for_the_customers_words(db, configuration):
    # D31 in the run of 2026-10-22: the agent proposed both scarves, or one it chose, without asking which.
    ctx = agent_for(db, "D31", configuration)
    said(ctx, SCARF)
    for n, units in enumerate((["d31-o1-u1"], ["d31-o1-u1", "d31-o1-u2"])):
        refused = call(ctx, "propose_refund", f"p-{n}", order_id="d31-o1", unit_ids=units)
        assert refused["refused"] == "units_named", refused
        assert "Linen scarf, olive (order d31-o1, placed 6 October, unit d31-o1-u1)" in refused["explanation"]
        assert "Linen scarf, rust (order d31-o1, placed 6 October, unit d31-o1-u2)" in refused["explanation"]
    assert proposals(ctx) == []
    rejected = "SELECT reason FROM audit_events WHERE event = 'propose' AND outcome = 'rejected'"
    assert rows(ctx.engine, rejected) == [("units_named",), ("units_named",)]  # recorded like any refused attempt
    gloves = call(ctx, "propose_refund", "p-gloves", order_id="d31-o1", unit_ids=["d31-o1-u3"])
    assert gloves["outcome"] == "refused"  # no look-alike: the policy decides (the gloves were not returned)
    said(ctx, "Which one would you like refunded, the olive or the rust one?", author="agent")
    said(ctx, "The olive one, please.")
    made = call(ctx, "propose_refund", "p-olive", order_id="d31-o1", unit_ids=["d31-o1-u1"])
    assert made["status"] == "awaiting_customer_confirmation"


# A fact line between the agent's offer or question and the customer's answer (review of 2026-10-28, verified on
# 795d430: D40 try 2 of 2026-10-27, a genuine yes refused). The line is said by the graph from the records after the
# agent's answer; it is not what the customer answers, and the checks that pair an answer with the message before it
# skip it.

DELIVERED_ONLY = (
    "Only orders recorded as delivered can be refunded through this process, and order d37-o1 is shipped "
    "(refund-policy/v2/eligible-orders)."
)


def test_a_yes_to_the_offer_of_a_person_counts_although_a_fact_line_came_between(db):
    ctx = agent_for(db, "D37")
    said(ctx, "Hello, my rice cooker order is still on its way, but I don't need it any more. Can I cancel it?")
    said(ctx, "Cancelling is outside this process. Would you like me to connect you with a staff member?", "agent")
    said(ctx, DELIVERED_ONLY, "agent", fact_line=True)
    said(ctx, "Yes, please.")
    accepted = asked(ctx, "Yes, please.")
    assert accepted["ok"] is True, accepted
    assert control(ctx) == [("human_controlled",)]


def test_a_yes_to_the_question_that_named_the_item_counts_although_a_fact_line_came_between(db):
    ctx = agent_for(db, "D31")
    said(ctx, SCARF)
    said(ctx, "Do you mean the olive scarf?", author="agent")
    said(ctx, "Each unit is refunded only once (refund-policy/v2/remaining).", "agent", fact_line=True)
    said(ctx, "Yes, that one.")
    made = call(ctx, "propose_refund", order_id="d31-o1", unit_ids=["d31-o1-u1"])
    assert made.get("status") == "awaiting_customer_confirmation", made


def test_items_the_customer_named_as_both_are_proposed_at_once(db):
    ctx = agent_for(db, "D32")
    said(ctx, "Hi, I sent back both linen scarves, the olive one and the rust one. Please refund both of them.")
    made = call(ctx, "propose_refund", order_id="d32-o1", unit_ids=["d32-o1-u1", "d32-o1-u2"])
    assert made["status"] == "awaiting_customer_confirmation"


def test_an_item_the_customer_named_by_its_order_date_is_proposed_at_once(db):
    ctx = agent_for(db, "D34")
    said(ctx, "Hello, I sent back the white ceramic planter from the order I placed on 5 October. Can I get my money?")
    assert call(ctx, "propose_refund", order_id="d34-o1", unit_ids=["d34-o1-u1"])["refused"] == "units_named"
    made = call(ctx, "propose_refund", "call-2", order_id="d34-o2", unit_ids=["d34-o2-u1"])
    assert made["status"] == "awaiting_customer_confirmation"


def test_a_refused_look_alike_leaves_the_open_proposal_and_a_repeated_call_as_they_were(db):
    ctx = agent_for(db, "D31")
    said(ctx, "I sent back the olive linen scarf. Can I have a refund?")
    olive = call(ctx, "propose_refund", "p-olive", order_id="d31-o1", unit_ids=["d31-o1-u1"])["proposal_id"]
    rust = call(ctx, "propose_refund", "p-rust", order_id="d31-o1", unit_ids=["d31-o1-u2"])
    assert rust["refused"] == "units_named"  # never named by the customer: it does not replace the open proposal
    assert proposals(ctx) == [("awaiting_customer_confirmation", ["d31-o1-u1"])]
    said(ctx, "Sorry, I am not sure any more.")
    again = call(ctx, "propose_refund", "p-olive", order_id="d31-o1", unit_ids=["d31-o1-u1"])  # after a restart
    assert again["proposal_id"] == olive


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
    mine = [o for o in scenario.fixture.orders if o.customer == customer]
    # The customer names every item and order, so a proposal among look-alikes is not refused for want of words.
    said(ctx, "; ".join(f"{u.product} in order {o.id}" for o in mine for u in o.units) + ". All of them.")
    for order in mine:
        units = [unit.id for unit in order.units]
        for n, selection in enumerate([[unit] for unit in units] + ([units] if len(units) > 1 else [])):
            before = counts(app)
            found = call(ctx, "assess_refund", f"a-{order.id}-{n}", order_id=order.id, unit_ids=selection)
            assert counts(app) == before, selection
            made = call(ctx, "propose_refund", f"p-{order.id}-{n}", order_id=order.id, unit_ids=selection)
            # The decision agrees. A new eligible proposal adds after it only the sections of its own circumstances
            # (refunds.proposal_context: its deadline, earlier requests for its units), which no assessment has, since
            # an assessment creates no proposal (D43, D46, D50, D52 and D60 have them).
            decided = len(found["policy_citations"])
            assert (found["outcome"], found["policy_citations"], found["amount_minor"]) == (
                made["outcome"],
                made["policy_citations"][:decided],
                made["amount_minor"],
            ), selection
            assert set(made["policy_citations"][decided:]) <= {WINDOW, VALIDITY, APPROVAL}, selection


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


# The second review (2026-10-22): the named case was keyed by the first refusal reason only.


@pytest.mark.parametrize("tool", ["assess_refund", "propose_refund"])
def test_a_late_request_for_a_unit_not_received_still_names_the_case_for_a_person(db, tool):
    ctx = agent_for(db, "D05")  # a late request; here the unit's return is not recorded either
    with db("owner").begin() as conn:
        conn.execute(text("UPDATE order_units SET received_back_at = NULL WHERE id = 'd05-o1-u1'"))
    refused = call(ctx, tool, order_id="d05-o1", unit_ids=["d05-o1-u1"])
    assert refused["policy_citations"] == ["refund-policy/v2/window", "refund-policy/v2/return"]
    assert "If the customer says these units were already sent, the policy names that case" in refused["next_step"]


@pytest.mark.parametrize("tool", ["assess_refund", "propose_refund"])
def test_an_order_on_its_way_names_no_case_for_a_person(db, tool):
    ctx = agent_for(db, "D38")  # shipped, so nothing is received back either
    refused = call(ctx, tool, order_id="d38-o1", unit_ids=["d38-o1-u1"])
    assert refused["policy_citations"] == ["refund-policy/v2/eligible-orders", "refund-policy/v2/return"]
    assert "for a person" not in refused["next_step"] and "return_disputed" not in refused["next_step"]


@pytest.mark.parametrize("tool", ["assess_refund", "propose_refund"])
def test_a_refusal_names_only_the_units_a_return_dispute_can_carry(db, tool):
    ctx = agent_for(db, "D03")  # u1 refunded before, u2 received back, u3 kept by the customer
    refused = call(ctx, tool, order_id="d03-o1", unit_ids=["d03-o1-u1", "d03-o1-u2", "d03-o1-u3"])
    assert refused["policy_citations"] == ["refund-policy/v2/remaining", "refund-policy/v2/return"]
    assert "If the customer says they already sent d03-o1-u3 (Crystal wine glass)," in refused["next_step"]
    assert "the order and only those units" in refused["next_step"]


# A proposal call made again with its call ID returns the proposal as it is now (second review, 2026-10-22).


def test_a_proposal_call_made_again_tells_the_proposals_status_now(db):
    ctx = agent_for(db, "D01")
    again = lambda: call(ctx, "propose_refund", "p-1", order_id="d01-o1", unit_ids=["d01-o1-u1"])  # noqa: E731
    proposal = again()["proposal_id"]
    assert again()["next_step"].startswith("The proposal is now on the customer's card, waiting for their button.")
    confirm(ctx.engine, Actor("customer", ctx.customer_id), proposal, "confirmed", ctx.clock(), POLICY)
    assert again()["next_step"].startswith("The customer already confirmed this proposal with the button;")
    decide(ctx.engine, Actor("staff", "d01-rui"), proposal, "approved", ctx.clock(), POLICY)
    assert again()["next_step"].startswith("A staff member already approved this proposal;")
    receipt = call(ctx, "execute_refund", "x-1")["receipt"]["receipt_number"]
    assert again()["next_step"].startswith(f"This proposal is already paid, receipt {receipt}.")
    assert {again()["proposal_id"]} == {proposal}
    assert rows(ctx.engine, "SELECT count(*) FROM proposals") == [(1,)]
    assert rows(ctx.engine, "SELECT count(*) FROM refund_operations") == [(1,)]


def test_a_proposal_call_made_again_after_a_cancel_or_the_deadline_says_nothing_waits(db):
    ctx = agent_for(db, "D01")
    again = lambda c: call(c, "propose_refund", "p-1", order_id="d01-o1", unit_ids=["d01-o1-u1"])  # noqa: E731
    proposal = again(ctx)["proposal_id"]
    later = replace(ctx, clock=lambda: ctx.clock() + timedelta(hours=POLICY.rules.proposal_ttl_hours))
    expired = again(later)  # past its deadline, before any write records it: the status and the step agree
    assert expired["status"] == "expired"
    assert expired["next_step"].startswith("This proposal is expired and nothing waits for the customer's button.")
    assert cancel(ctx.engine, Actor("customer", ctx.customer_id), proposal, ctx.clock(), POLICY) == "cancelled"
    cancelled = again(ctx)
    assert cancelled["status"] == "cancelled"
    assert cancelled["next_step"].startswith("This proposal is cancelled and nothing waits for the customer's button.")
    assert rows(ctx.engine, "SELECT count(*) FROM proposals") == [(1,)]


def test_a_proposal_call_made_again_after_a_rejection_gives_the_reason_and_asks_for_nothing(db):
    ctx = agent_for(db, "D01")
    again = lambda: call(ctx, "propose_refund", "p-1", order_id="d01-o1", unit_ids=["d01-o1-u1"])  # noqa: E731
    proposal = again()["proposal_id"]
    confirm(ctx.engine, Actor("customer", ctx.customer_id), proposal, "confirmed", ctx.clock(), POLICY)
    reason = "The mug in the photo is not the one we sent."
    decide(ctx.engine, Actor("staff", "d01-rui"), proposal, "rejected", ctx.clock(), POLICY, reason)
    rejected = again()
    assert rejected["status"] == "rejected"
    assert rejected["next_step"] == (
        f'A staff member rejected this proposal, with the reason "{reason}". Tell the customer it was rejected and '
        "why; nothing waits for their button."
    )
    assert "propose_refund" not in rejected["next_step"]


def test_a_paid_refund_is_told_against_the_original_payment_and_the_ledger_only_when_asked(db):
    ctx = agent_for(db, "D01")
    proposal = call(ctx, "propose_refund", order_id="d01-o1", unit_ids=["d01-o1-u1"])["proposal_id"]
    approve(ctx, proposal, staff="d01-rui")
    paid = call(ctx, "execute_refund", "x-1")
    assert paid["next_step"].startswith("The refund is paid and recorded against the order's original payment.")
    assert "only if the customer asks when or how the money arrives" in paid["next_step"]
    assert paid["receipt"]["payment_id"] == "d01-o1-p1"  # the original payment the words refer to
