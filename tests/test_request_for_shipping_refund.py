"""When a request to refund shipping goes to a person (refunds.request_for_shipping_refund).

Review of the model comparison, 2026-10-24: the check took any words of the customer's latest message that name the
shipping charge, so "Will the shipping I paid be refunded too, or just the kettle?" handed D39 off in all three tries
of Luna none (2026-10-23), and a free probe found a negation, a hypothetical and a past event taken the same way.
Telling a question from a request in code would be one more list of words; instead the handoff rests on the customer's
yes to the agent's offer of a staff member for the shipping charge, made in the message just before. A question is
then answered from the shipping section, and a request costs the customer one more message: the yes.

Each case is a conversation, C for the customer and A for the agent, and whether its last message is a request to
refund shipping, with the agent quoting the whole of it.
"""

import pytest

from refund_agent.refunds import request_for_shipping_refund

OFFER = "Shipping is never refunded automatically. Would you like a staff member to review the shipping charge?"

CASES = {
    # Words alone, with no offer before them: the probe of 2026-10-24 and D40's request.
    "a question whether shipping is refunded (D39)": (
        [("C", "Hi, I returned the glass kettle. Will the shipping I paid be refunded too, or just the kettle?")],
        False,
    ),
    "a request, before any offer": ([("C", "Please refund the shipping charge too.")], False),
    "a request worded as a question, before any offer": ([("C", "Can you refund the shipping charge too?")], False),
    "a request, before any offer (D40)": ([("C", "I paid 18 reais shipping. I want the shipping refunded.")], False),
    "shipping excluded": ([("C", "I do not want the shipping refunded; just refund the kettle.")], False),
    "a hypothetical": ([("C", "If shipping were refunded, where would that money go?")], False),
    "a past event": ([("C", "A staff member refunded shipping on my previous order.")], False),
    # The customer's answer to an offer.
    "yes to an offer for the shipping charge": (
        [("C", "Will shipping be refunded?"), ("A", OFFER), ("C", "Yes, please.")],
        True,
    ),
    "yes to a wish-form offer": (
        [
            ("C", "And the shipping?"),
            ("A", "If you'd like, a staff member can review the shipping charge."),
            ("C", "Sure."),
        ],
        True,
    ),
    "a yes that goes on about something else": (
        [("C", "And the shipping?"), ("A", OFFER), ("C", "Yes, please. The kettle's lid was broken too.")],
        True,
    ),
    "no to the offer": ([("C", "And the shipping?"), ("A", OFFER), ("C", "No thanks, just the kettle.")], False),
    "a yes taken back in its sentence": ([("C", "And the shipping?"), ("A", OFFER), ("C", "Yes, but not now.")], False),
    "a yes withdrawn after it": (
        [("C", "And the shipping?"), ("A", OFFER), ("C", "Sure. Actually, never mind.")],
        False,
    ),
    "yes to an offer of a person for something else": (
        [
            ("C", "Can I cancel my other order? And will shipping be refunded?"),
            ("A", "Shipping is never refunded automatically. Would you like a staff member to help with cancelling?"),
            ("C", "Yes, please."),
        ],
        False,
    ),
    "yes to an offer about shipping that offers no person": (
        [("C", "And the shipping?"), ("A", "Would you like me to explain the shipping section?"), ("C", "Yes.")],
        False,
    ),
    "an offer that is withdrawn in its sentence": (
        [
            ("C", "And the shipping?"),
            ("A", "I can't connect you with a staff member about the shipping charge."),
            ("C", "Yes."),
        ],
        False,
    ),
    "yes to an offer made earlier, not just before": (
        [("C", "And the shipping?"), ("A", OFFER), ("C", "Let me think."), ("A", "Of course."), ("C", "Yes.")],
        False,
    ),
}


def conversation(turns):
    return [(f"m{n}", "customer" if who == "C" else "agent", words) for n, (who, words) in enumerate(turns)]


def latest_request(turns, words=None):
    messages = conversation(turns)
    latest = [m for m in messages if m[1] == "customer"][-1]
    return messages, latest, request_for_shipping_refund(messages, latest[2] if words is None else words)


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_request_to_refund_shipping_is_a_yes_to_an_offer(case):
    turns, holds = CASES[case]
    _, latest, (found, why) = latest_request(turns)
    assert (found is not None) == holds, why
    assert found in (None, latest[0])


def test_a_quote_that_leaves_out_a_negation_does_not_hide_it():
    # The agent quotes "Yes" from "Yes, but not for the shipping.": the whole message is read, not the quote.
    turns = [("C", "And the shipping?"), ("A", OFFER), ("C", "Yes, but not for the shipping.")]
    assert latest_request(turns, "Yes")[2][0] is None


def test_each_refusal_says_what_is_missing():
    no_offer = latest_request([("C", "I want the shipping refunded.")])[2][1]
    assert no_offer.startswith("that message is not a yes to your offer of a staff member for the shipping charge")
    yes_without_offer = latest_request([("C", "And shipping?"), ("A", "Anything else?"), ("C", "Yes.")])[2][1]
    assert yes_without_offer.startswith(
        "that message is a yes, but your message just before it offers no staff member for the shipping charge"
    )
    assert latest_request([("C", "Yes.")], "")[2][1].startswith(
        "customer_words must give the customer's own words that accept, with a yes, your offer of a staff member"
    )
