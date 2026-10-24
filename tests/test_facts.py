"""The fact line after an answer (refund_agent.agent.facts): a fact the agent states, with the policy section it rests
on, rendered from the tool results (review of the model comparison, 2026-10-24).

The conversations are reduced from the runs of 2026-10-23: D20 (both items refunded before the conversation; Luna gave
the receipt and the payout section and left out the remaining section in tries 1 and 2), D35 (an order on its way;
Luna try 2 cited nothing, Sol try 2 cited the exceptions section), D25 (a receipt paid in this conversation) and D19
(the section cited in an earlier answer).
"""

import json

from refund_agent.agent.facts import fact_line
from refund_agent.policy import load_policy

POLICY = load_policy()
REMAINING, ELIGIBLE = "refund-policy/v2/remaining", "refund-policy/v2/eligible-orders"


def orders(*entries):
    return {
        "role": "tool",
        "call_id": "c1",
        "name": "list_my_orders",
        "content": json.dumps({"ok": True, "orders": list(entries)}),
    }


def order(order_id, status, requests=()):
    return {"order_id": order_id, "status": status, "units": [], "requests": list(requests)}


PAID_BEFORE = orders(
    order("h10-o1", "delivered", [{"proposal_id": "d20-r1", "status": "refunded", "receipt_number": "R-H10-0001"}])
)
ON_ITS_WAY = orders(order("d35-o1", "shipped"))


def agent(text_):
    return {"role": "agent", "text": text_, "tool_calls": [], "continuation": []}


def test_a_receipt_paid_before_the_conversation_gets_the_remaining_section():
    # D20 try 1 of Luna none.
    answer = "Both items have already been refunded: BRL 157.90 total. The receipt number is **R-H10-0001**."
    line = fact_line([PAID_BEFORE], answer, POLICY)
    assert "R-H10-0001" in line and REMAINING in line


def test_an_answer_that_cites_the_section_gets_nothing():
    # D20 try 3 of Luna none, and every D20 answer of Sol low.
    answer = "Refunded under receipt **R-H10-0001**. The items can't be refunded again (refund-policy/v2/remaining)."
    assert fact_line([PAID_BEFORE], answer, POLICY) == ""


def test_a_section_cited_earlier_in_the_conversation_is_not_repeated():
    # D20 try 3: the customer then asked for the receipt number again.
    first = agent("Refunded, receipt R-H10-0001; it cannot be refunded again (refund-policy/v2/remaining).")
    assert fact_line([PAID_BEFORE, first], "The receipt number is **R-H10-0001**.", POLICY) == ""


def test_a_receipt_paid_in_this_conversation_gets_nothing():
    # D25: the strap was paid here, and the agent repeats its receipt when asked about the watch.
    paid = {
        "role": "tool",
        "call_id": "c2",
        "name": "execute_refund",
        "content": json.dumps({"ok": True, "receipt": {"receipt_number": "R-00000001", "amount_minor": 3900}}),
    }
    listed = orders(
        order("h15-o1", "delivered", [{"proposal_id": "p1", "status": "refunded", "receipt_number": "R-00000001"}])
    )
    answer = "Only the silicone watch strap was refunded (BRL 39.00, receipt **R-00000001**)."
    assert fact_line([paid, listed], answer, POLICY) == ""


def test_an_order_on_its_way_gets_the_eligible_orders_section():
    # D35 try 2 of Luna none, and of Sol low with the exceptions section.
    for answer in (
        "Your reading lamp order is currently marked as **shipped**, not delivered. A staff member can help.",
        "Your reading lamp order **d35-o1** is marked **shipped**, not delivered (refund-policy/v2/exceptions).",
    ):
        line = fact_line([ON_ITS_WAY], answer, POLICY)
        assert "d35-o1" in line and "shipped" in line and ELIGIBLE in line


def test_a_status_word_counts_only_for_an_order_with_that_status_not_delivered():
    delivered = orders(order("d01-o1", "delivered"))
    assert fact_line([delivered], "It was shipped on the 2nd and delivered on the 5th.", POLICY) == ""
    # A word of a proposal's status is not an order's: "approved" and "canceled" are left out on purpose.
    approved = orders(order("x-o1", "approved"))
    assert fact_line([approved], "A staff member approved it, so it is ready to be paid.", POLICY) == ""


def test_both_facts_go_in_one_line_and_each_cites_its_section():
    both = orders(
        order("h10-o1", "delivered", [{"proposal_id": "d20-r1", "status": "refunded", "receipt_number": "R-H10-0001"}]),
        order("d35-o1", "shipped"),
    )
    line = fact_line([both], "Receipt R-H10-0001 is paid; your lamp is shipped.", POLICY)
    assert REMAINING in line and ELIGIBLE in line
