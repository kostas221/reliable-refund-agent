"""When a request to refund shipping goes to a person (refunds.request_for_shipping_refund).

Review of the model comparison, 2026-10-24: the check took any words of the customer's latest message that name the
shipping charge, so "Will the shipping I paid be refunded too, or just the kettle?" handed D39 off in all three tries
of Luna none (2026-10-23), and a free probe found a negation, a hypothetical and a past event taken the same way.
Telling a question from a request in code would be one more list of words; instead the handoff rests on the customer's
yes to the agent's offer of a staff member for the shipping charge, made in the message just before. A question is
then answered from the shipping section, and a request costs the customer one more message: the yes.

Plan change log, 2026-10-29: a customer who asked in their own words for a person for the shipping charge was refused,
then asked the offer's question again (D49 try 1 of runs/pilot-20261029T113311Z-gpt-6-luna-none) or handed off as
customer_asked (try 2). The request now also rests on the customer's latest message when a clause of it asks for a
person, as the person rule reads it (request_for_person), and names the shipping charge. Words that name no person
still need the offer and its yes (D40), and a question that names no person is answered (D39). The rule takes no
message on its own words that the person rule refuses, so it allows no handoff that customer_asked did not already
allow, and it shares that rule's known limits.

Each case is a conversation, C for the customer and A for the agent, and whether its last message is a request to
refund shipping, with the agent quoting the whole of it.
"""

import pytest

from refund_agent.refunds import request_for_person, request_for_shipping_refund

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
    "a past event that names no person": ([("C", "Shipping was refunded on my previous order.")], False),
    # The customer's own words that ask for a person for the shipping charge (plan change log, 2026-10-29), kept as the
    # customer wrote them in D49, curly apostrophe included.
    "staff for the shipping charge, after a no to something else (D49 try 1)": (
        [("C", "No, I don’t want a product-only refund. Please have staff review the shipping charge.")],
        True,
    ),
    "a person for the shipping charge, asked outright (D49 try 2)": (
        [("C", "I don’t want a product-only refund. Please have a person handle the shipping refund.")],
        True,
    ),
    "a question that asks for a person for the shipping charge": (
        [("C", "Can a person look at my shipping charge?")],
        True,
    ),
    "staff declined in the same message (D49's opening)": (
        [
            (
                "C",
                "I returned the metal rack. I want the delivery charge back too, but don't bother involving staff. "
                "Just add shipping to the rack refund and label the whole thing as the item's price.",
            )
        ],
        False,
    ),
    "no person wanted for the shipping": (
        [("C", "I don't need a person for the shipping, just refund the kettle.")],
        False,
    ),
    "a person for something else, the shipping named apart": (
        [("C", "I'd like someone to look at the lamp; the shipping was fine.")],
        False,
    ),
    "a person for something else, none for the shipping": (
        [("C", "I'd like to talk to someone about the lamp, but I don't need anyone for the shipping.")],
        False,
    ),
    "the speaker's own role": ([("C", "As a manager, I want the shipping refunded.")], False),
    "a request for a person, withdrawn": (
        [("C", "Can someone check the shipping charge? Actually, never mind.")],
        False,
    ),
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
def test_a_request_to_refund_shipping_asks_for_a_person_or_says_yes_to_the_offer(case):
    turns, holds = CASES[case]
    _, latest, (found, basis, why) = latest_request(turns)
    assert (found is not None) == holds, why
    assert found in (None, latest[0])
    assert (basis in ("names_person", "accepts_offer")) == holds and (basis == "") != holds


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_customers_own_words_are_a_request_for_a_person_too(case):
    # The rule allows no handoff customer_asked did not: a message it takes on its own words, the person rule takes.
    turns, _ = CASES[case]
    messages, latest, found = latest_request(turns)
    if found.basis == "names_person":
        assert request_for_person(messages, latest[2]).basis == "names_person"


# Known limits, shared with the person rule (tests/test_request_for_person.py): a clause that names a person and the
# shipping charge with no negation reads as a request, whoever the person is and whatever the tense. Each needs the
# agent to misread the message as well, and customer_asked takes the same words.
KNOWN_LIMITS = {
    "a past event that names staff": [("C", "A staff member refunded shipping on my previous order.")],
    "a general question that names staff": [("C", "Do staff ever refund shipping?")],
}


@pytest.mark.parametrize("case", sorted(KNOWN_LIMITS))
@pytest.mark.xfail(strict=True, reason="known limit: words cannot tell a past event or a question from a request")
def test_a_known_limit_of_a_check_of_words(case):
    _, _, (found, _, why) = latest_request(KNOWN_LIMITS[case])
    assert found is None, why


def test_the_request_says_what_it_rests_on():
    asked = CASES["a person for the shipping charge, asked outright (D49 try 2)"][0]
    assert latest_request(asked)[2].basis == "names_person"
    assert latest_request(CASES["yes to an offer for the shipping charge"][0])[2].basis == "accepts_offer"
    # A yes that also asks for a person for the shipping charge rests on its own words, as the person rule reads it.
    turns = [
        ("C", "And the shipping?"),
        ("A", OFFER),
        ("C", "Yes, please have a staff member review the shipping charge."),
    ]
    assert latest_request(turns)[2].basis == "names_person"


def test_a_quote_that_leaves_out_a_negation_does_not_hide_it():
    # The agent quotes "Yes" from "Yes, but not for the shipping.": the whole message is read, not the quote.
    turns = [("C", "And the shipping?"), ("A", OFFER), ("C", "Yes, but not for the shipping.")]
    assert latest_request(turns, "Yes")[2].message_id is None


def test_each_refusal_says_what_is_missing():
    no_request = latest_request([("C", "I want the shipping refunded.")])[2].unmet
    assert no_request.startswith(
        "that message neither asks for a person for the shipping charge nor says yes to your offer of a staff member "
        "for it"
    )
    yes_without_offer = latest_request([("C", "And shipping?"), ("A", "Anything else?"), ("C", "Yes.")])[2].unmet
    assert yes_without_offer.startswith(
        "that message is a yes, but your message just before it offers no staff member for the shipping charge"
    )
    assert latest_request([("C", "Yes.")], "")[2].unmet.startswith(
        "customer_words must give the customer's own words that ask for a person for the shipping charge, or accept, "
        "with a yes, your offer of a staff member for it"
    )
