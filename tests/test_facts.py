"""The fact line after an answer (refund_agent.agent.facts): a fact the agent states, with the policy section it rests
on, rendered from the tool results (review of the model comparison, 2026-10-24).

The conversations are reduced from the runs of 2026-10-23: D20 (both items refunded before the conversation; Luna gave
the receipt and the payout section and left out the remaining section in tries 1 and 2), D35 (an order on its way;
Luna try 2 cited nothing, Sol try 2 cited the exceptions section), D25 (a receipt paid in this conversation) and D19
(the section cited in an earlier answer).
"""

import json

from refund_agent.agent.facts import HANDOFF_CASES, fact_line
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


def order(order_id, status, requests=(), products=()):
    units = [{"unit_id": f"{order_id}-u{n}", "product": product} for n, product in enumerate(products, 1)]
    return {"order_id": order_id, "status": status, "units": units, "requests": list(requests)}


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


# The latest read of each order, and only an order the answer names (review of 2026-10-28, verified on 795d430: the line
# kept a status a later read had replaced, and named an order the answer was not about).

SCANNER = order("h80-o1", "delivered", products=["Portable document scanner"])
SLEEVE = order("h80-o2", "shipped", products=["Laptop carrying sleeve"])


def test_a_later_read_of_the_same_order_replaces_the_earlier_one():
    history = [orders(order("o1", "shipped")), orders(order("o1", "delivered"))]
    answer = "The previous record said shipped, but the latest record now says delivered."
    assert fact_line(history, answer, POLICY) == ""


def test_a_failed_read_does_not_erase_what_an_earlier_read_showed():
    failed = {"role": "tool", "call_id": "c3", "name": "get_my_order", "content": json.dumps({"ok": False})}
    line = fact_line([ON_ITS_WAY, failed], "Your reading lamp order is still shipped.", POLICY)
    assert "d35-o1 is shipped" in line


def test_an_answer_about_another_order_gets_nothing():
    # "shipped" in another sense, about the delivered order, while the other order is on its way: named by a word of
    # its product and its ID, or by its ID alone.
    for answer in (
        "Your scanner from order h80-o1 was shipped back to us and received.",
        "Order h80-o1 was shipped back to us and received.",
    ):
        assert fact_line([orders(SCANNER, SLEEVE)], answer, POLICY) == ""


def test_a_read_without_its_units_keeps_the_words_of_the_earlier_one():
    bare = {key: value for key, value in SLEEVE.items() if key != "units"}
    answer = "Your scanner was received, and your laptop sleeve is still shipped."  # both named, each by its words
    line = fact_line([orders(SCANNER, SLEEVE), orders(bare)], answer, POLICY)
    assert "order h80-o2 is shipped" in line
    answer = "Your scanner was shipped back to us."  # the scanner is named, so nothing is said of the sleeve
    assert fact_line([orders(SCANNER, SLEEVE), orders(bare)], answer, POLICY) == ""


def test_an_order_named_by_its_product_or_its_id_gets_the_line():
    # D62 try 1: the sleeve order named by words of its product; and by its ID.
    for answer in (
        "A person will help with your laptop sleeve order, which is still being shipped.",
        "h80-o2 is shipped.",
    ):
        line = fact_line([orders(SCANNER, SLEEVE)], answer, POLICY)
        assert "order h80-o2 is shipped" in line and "h80-o1" not in line


def test_a_word_two_orders_share_names_neither():
    # "electric" is in both products: it tells neither order apart, so only "kettle" names one, the delivered one.
    kettle = order("o1", "delivered", products=["Electric kettle"])
    cooker = order("o2", "shipped", products=["Electric rice cooker"])
    answer = "Your electric kettle was shipped back to us and received."
    assert fact_line([orders(kettle, cooker)], answer, POLICY) == ""


def test_an_answer_that_names_no_order_counts_for_the_one_on_its_way():
    line = fact_line([orders(SCANNER, SLEEVE)], "Your order is shipped, not delivered yet.", POLICY)
    assert "order h80-o2 is shipped" in line


# A handoff's section (final evaluation of v1.1, 2026-10-26). Every refusal's tool result gave its sections, and all 98
# required refusal citations of the runs on policy v2 were shown; a handoff's result gave none, and 11 of 18 required
# handoff citations were missed (H72, H80: the customer asked for a person, and the announcement left out the section).

EXCEPTIONS, WINDOW, PAYMENT = "refund-policy/v2/exceptions", "refund-policy/v2/window", "refund-policy/v2/payment"


def handed_off(code, citations, ok=True):
    result = (
        {"ok": True, "handoff_id": "hand-1", "reason_code": code, "policy_citations": list(citations)}
        if ok
        else {"ok": False, "refused": "handoff_reason", "explanation": "not a case the policy names"}
    )
    return {"role": "tool", "call_id": "h1", "name": "request_handoff", "content": json.dumps(result)}


def test_a_handoff_announced_without_its_section_gets_it():
    # H80 try 1 of Luna none: "A person will take over from here."
    line = fact_line([handed_off("customer_asked", [EXCEPTIONS])], "A person will take over from here.", POLICY)
    assert line == f"A person takes over whenever you ask for one ({EXCEPTIONS})."


def test_each_kind_of_handoff_says_its_own_case():
    for code, case in (
        ("shop_decided", "Under the policy, a staff member decides this request"),
        ("return_disputed", "A staff member reviews units you say were sent but are not recorded as received back"),
        ("delivery_disputed", "A staff member reviews an order recorded as delivered that you say never arrived"),
        ("shipping_refund", "A staff member reviews a request to refund the shipping charge"),
    ):
        line = fact_line([handed_off(code, [WINDOW])], "A person will take over.", POLICY)
        assert line == f"{case} ({WINDOW}).", code


def test_a_handoff_announced_with_its_section_gets_nothing():
    answer = f"A person takes over whenever you ask for one ({EXCEPTIONS}). They will be with you shortly."
    assert fact_line([handed_off("customer_asked", [EXCEPTIONS])], answer, POLICY) == ""


def test_only_the_sections_not_cited_yet_are_said():
    # D10: the agent explained the late request with the window section before it handed off.
    first = agent(f"Your request is past the 30-day limit ({WINDOW}), but an earlier one was made in time.")
    history = [first, handed_off("shop_decided", [WINDOW, PAYMENT])]
    assert fact_line(history, "A person will take over.", POLICY) == (
        f"Under the policy, a staff member decides this request ({PAYMENT})."
    )
    assert fact_line([first, handed_off("shop_decided", [WINDOW])], "A person will take over.", POLICY) == ""


def test_a_refused_handoff_gets_nothing():
    assert fact_line([handed_off("customer_asked", [], ok=False)], "I can't hand this over.", POLICY) == ""


def test_every_reason_for_a_handoff_has_its_case_and_its_sections():
    from refund_agent.agent.tools import HANDOFF_SECTIONS
    from refund_agent.refunds import HANDOFF_REASONS

    assert set(HANDOFF_CASES) == set(HANDOFF_REASONS)
    assert set(HANDOFF_SECTIONS) | {"shop_decided"} == set(HANDOFF_REASONS)  # shop_decided: the decision's reasons
    assert all(POLICY.citation(section) for sections in HANDOFF_SECTIONS.values() for section in sections)


# A question the customer asked about a rule, answered without the section the policy says answers it (citation rule,
# case d; v1.3, plan change log 2026-10-31). From the confirmation run of 2026-10-31 and the reasoning runs before it:
# D69 (shipping answered under amount), D41 (where the money goes, under payout) and D72 (a cancelled card, under no
# section). The line comes only when the customer asked, so a receipt that says "original payment" adds nothing.

SHIPPING, APPROVAL = "refund-policy/v2/shipping", "refund-policy/v2/approval"
SHIPPING_LINE = f"Shipping charges are never refunded automatically ({SHIPPING})."  # the section's own words
PAYMENT_LINE = f"A refund goes only to the order's original payment ({PAYMENT})."
APPROVAL_LINE = (
    "A cancelled or rejected proposal pays nothing, and every new proposal needs its own confirmation with its card's "
    f"button and a staff member's approval ({APPROVAL})."
)


def customer(text_):
    return {"role": "customer", "text": text_}


YOGA = customer("Of my two returned purchases, refund only the older yoga mat. Is the delivery fee part of that?")
MOUSE = customer("Does the money go back to my card or to store credit?")
TOWEL = customer("Last week I cancelled a refund card for the bath towel. Does the cancelled card matter?")


def test_a_shipping_question_answered_without_its_section_gets_it():
    answer = (
        "The delivery fee isn't included; shipping charges aren't part of the item refund (refund-policy/v2/amount)."
    )
    assert fact_line([YOGA], answer, POLICY) == SHIPPING_LINE


def test_where_the_money_goes_answered_without_its_section_gets_it():
    answer = (
        "The refund was recorded against the order's original payment, not as store credit (refund-policy/v2/payout)."
    )
    assert fact_line([MOUSE], answer, POLICY) == PAYMENT_LINE


def test_a_cancelled_card_question_answered_without_its_section_gets_it():
    answer = "The cancelled bath-towel card doesn't count as an active refund request. I've proposed BRL 149.99."
    assert fact_line([TOWEL], answer, POLICY) == APPROVAL_LINE


def test_an_answer_that_cites_the_section_the_question_asks_gets_nothing():
    assert fact_line([YOGA], f"Shipping isn't included ({SHIPPING}).", POLICY) == ""
    assert fact_line([MOUSE], f"It goes to the original payment ({PAYMENT}).", POLICY) == ""
    assert fact_line([TOWEL], f"It doesn't matter; confirm the new card ({APPROVAL}).", POLICY) == ""


def test_a_section_cited_earlier_is_not_said_again():
    earlier = agent(f"Shipping charges aren't refunded automatically ({SHIPPING}).")
    assert fact_line([earlier, YOGA], "The delivery fee isn't included.", POLICY) == ""


def test_the_same_words_with_no_question_from_the_customer_get_nothing():
    # Every receipt says "original payment"; a fact line after each would be noise.
    hello = customer("Hi, I sent back the wireless mouse. Could I get a refund?")
    receipt = "Your refund of BRL 69.90 has been paid to the order's original payment. Receipt: R-00000001."
    assert fact_line([hello], receipt, POLICY) == ""
    assert fact_line([hello], "Shipping charges aren't part of the item refund.", POLICY) == ""
    assert fact_line([hello], "The cancelled card is closed.", POLICY) == ""


def test_an_answer_that_does_not_speak_of_it_gets_nothing():
    assert fact_line([YOGA], "I've proposed BRL 145.00 for the yoga mat.", POLICY) == ""
    assert fact_line([MOUSE], "Your receipt number is R-00000001.", POLICY) == ""


def test_an_order_shipped_or_the_proposal_card_is_not_such_a_question():
    shipped = customer("My controller was shipped last week. Where is it?")
    assert SHIPPING not in fact_line([shipped], "It was shipped; I can't see where it is.", POLICY)
    card = customer("Is that the right proposal card? I'll confirm it.")
    assert fact_line([card], "Yes. Once paid, it goes to the order's original payment.", POLICY) == ""


def test_the_question_is_the_customers_latest_message():
    later = customer("Thanks. And is the receipt number the one above?")
    assert fact_line([MOUSE, agent("It goes to the original card."), later], "Yes, original payment.", POLICY) == ""


def test_a_reply_to_an_event_is_not_an_answer_to_the_customers_words():
    # D54 and H55 (22 answers in the saved runs): "your account page" is the shop's site, and the receipt answers the
    # staff decision, not the customer.
    lunch_box = customer("Your account page seems to show you received it. If your records confirm it, refund it?")
    approved = {"role": "event", "text": "The customer confirmed request prop-1 and a staff member approved it."}
    receipt = "The BRL 25.00 refund has been paid to the order's original payment. Receipt: R-00000001."
    assert fact_line([lunch_box, approved], receipt, POLICY) == ""
    assert fact_line([lunch_box], "It will go to the original payment.", POLICY) == ""  # "account" alone says nothing
    # A question about the card, then the staff decision: the receipt replies to the decision.
    card = customer("Could you refund the mouse to my card?")
    assert fact_line([card], receipt, POLICY) == PAYMENT_LINE
    assert fact_line([card, agent("I've proposed BRL 69.90 for the mouse."), approved], receipt, POLICY) == ""


def test_a_statement_with_no_question_gets_nothing():
    # D77 try 2 (2026-10-31): the customer stated that shipping is excluded and asked nothing.
    strap = customer("The black wrist strap, please. I understand the refund is its paid amount, excluding shipping.")
    answer = "The proposal is BRL 28.45, its paid amount after the discount share and excluding shipping."
    assert fact_line([strap], answer, POLICY) == ""


def test_a_cancelled_bank_card_is_a_question_of_where_the_money_goes():
    bank = customer("I cancelled my credit card last month. Where will the refund go?")
    answer = "Even with the card cancelled, it goes to the original payment; your card's issuer handles the credit."
    assert fact_line([bank], answer, POLICY) == PAYMENT_LINE  # a cancelled bank card is not a cancelled refund card
