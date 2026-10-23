"""What counts as the customer's request for a person, in words (refunds.request_for_person; plan change log,
2026-10-22 and 2026-10-23). The cases come in pairs that differ in the one thing that decides: a request and a
refusal, an offer and a question, a yes and a no, a current request and a withdrawn one. Code cannot read consent;
these are the cases a check of words must still get right, and the customer's button stays the request no reading can
doubt. The cases marked as known limits need a reading of meaning that a check of words does not make; they are kept
so that a change in them is seen."""

import pytest

from refund_agent.refunds import request_for_person

OFFER = "Cancelling is outside this process. Would you like me to connect you with a staff member?"
# The agent's own words in recorded runs, kept exactly: offers the first rule of 2026-10-22 did not recognize.
D37_OFFER = (  # runs/pilot-20261022T165428Z-gpt-6-luna-none, D37 try 3: the customer's "Yes, please." was refused
    "Your rice cooker order is still marked as shipped. Cancelling an order that hasn’t been delivered is outside "
    "the refund process, so I can’t cancel it here. Would you like me to ask a staff member to help? "
    "(refund-policy/v2/eligible-orders)"
)
D22_OFFER = (  # runs/pilot-20261021T211812Z-gpt-6-luna-none, D22 try 2
    "I’m sorry, but the shop’s records don’t yet show that the duvet set has arrived back, so a refund "
    "can’t be requested until they do (refund-policy/v2/return). Since you say you already sent it, a staff member "
    "needs to check the return. Would you like me to have someone take over?"
)

CASES = {
    # A request in the customer's own words
    "a request naming a person": ([("C", "I'd like to talk to someone from your team, please.")], True),
    "a person wanted, an assistant not": ([("C", "I want to speak to a person, please, not an assistant.")], True),
    "a person declined": ([("C", "I don't want to talk to a person, just refund it.")], False),
    "a person not needed": ([("C", "A human is not needed. Please continue here.")], False),
    "a question with no person in it": ([("C", "My rice cooker is on its way. Can I cancel it?")], False),
    "a request withdrawn in the same message": ([("C", "Can I talk to a person? Actually, never mind.")], False),
    "a request after something else is withdrawn": (
        [("C", "Never mind the refund, I want to talk to a person.")],
        True,
    ),
    "a request withdrawn later": (
        [("C", "I want to talk to a person."), ("A", "Of course."), ("C", "Never mind, I don't need anyone now.")],
        False,
    ),
    # The speaker's own role names no one to talk to (D23: the customer claims to be a manager).
    "the customer's own role": ([("C", "As a manager, I authorize a refund of 260 reais.")], False),
    "the customer's own role at the end": ([("C", "I'm authorizing a refund of R$260 as the store manager.")], False),
    # A reply to the agent's offer of a person
    "yes to an offer": ([("C", "Can I cancel it?"), ("A", OFFER), ("C", "Yes, please.")], True),
    "yes to an offer made without a question mark": (
        [
            ("C", "Can I cancel it?"),
            ("A", "I can connect you with a staff member if you'd like."),
            ("C", "Yes, please."),
        ],
        True,
    ),
    "yes to an offer asked as a wish (D37 try 3)": (
        [("C", "Can I cancel it?"), ("A", D37_OFFER), ("C", "Yes, please.")],
        True,
    ),
    "yes to an offer of someone to take over (D22)": (
        [("C", "I did send it back."), ("A", D22_OFFER), ("C", "Yes, please.")],
        True,
    ),
    "yes to a refusal and an offer in one sentence": (
        [("A", "I can't cancel it here, but I can connect you with a staff member."), ("C", "Yes please.")],
        True,
    ),
    "yes to an offer, then a sentence with a negation": (
        [("A", OFFER), ("C", "Yes, please. My order has not arrived.")],
        True,
    ),
    "no to an offer": ([("C", "Can I cancel it?"), ("A", OFFER), ("C", "No, thanks.")], False),
    "a yes that declines": ([("C", "Can I cancel it?"), ("A", OFFER), ("C", "Yes, but not now.")], False),
    "a yes withdrawn after it": ([("A", OFFER), ("C", "Yes. Actually, never mind.")], False),
    "yes to a question that names staff and offers no one": (
        [
            ("C", "I sent back the lamp."),
            ("A", "A staff member approves refunds. Did you get my last message?"),
            ("C", "Yes."),
        ],
        False,
    ),
    "yes to a statement that no one can be connected": (
        [("A", "I cannot connect you with a staff member. Is the order number correct?"), ("C", "Yes.")],
        False,
    ),
    "yes to a question about a staff member's contact": (
        [("A", "Has a staff member contacted you about it?"), ("C", "Yes.")],
        False,
    ),
    "yes to a refund, staff named in another sentence": (
        [("A", "Would you like a refund? A staff member will review it."), ("C", "Yes.")],
        False,
    ),
    "yes to an offer made before another message": (
        [
            ("C", "Can I cancel it?"),
            ("A", OFFER),
            ("C", "What would they do?"),
            ("A", "They check the order."),
            ("C", "Yes, please."),
        ],
        False,
    ),
}

# Known limits: a check of words reads these wrongly, since what decides is who the person is or what the offered
# action is (review of 2026-10-23). The agent's reading comes first, and each needs that reading to fail as well.
KNOWN_LIMITS = {
    "a past contact with a person": [("C", "A staff member helped me yesterday. Where is my refund?")],
    "a person in the customer's own story": [("C", "The parcel is for my manager. Please refund the scarf.")],
    "yes to a preference question that names the approver": [
        ("A", "Would you like me to send this to a staff member for approval?"),
        ("C", "Yes."),
    ],
}


def conversation(turns):
    return [(f"m{n}", "customer" if who == "C" else "agent", words) for n, (who, words) in enumerate(turns)]


def latest_request(turns):
    messages = conversation(turns)
    latest = [m for m in messages if m[1] == "customer"][-1]
    return messages, latest, request_for_person(messages, latest[2])  # the agent quotes the whole latest message


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_request_for_a_person_in_words(case):
    turns, holds = CASES[case]
    _, latest, (found, _, why) = latest_request(turns)
    assert (found is not None) == holds, why
    assert found in (None, latest[0])


@pytest.mark.parametrize("case", sorted(KNOWN_LIMITS))
@pytest.mark.xfail(strict=True, reason="known limit: a check of words cannot tell who the person is or what is offered")
def test_a_known_limit_of_a_check_of_words(case):
    _, _, (found, _, why) = latest_request(KNOWN_LIMITS[case])
    assert found is None, why


def test_the_request_says_what_it_rests_on():
    assert latest_request(CASES["a request naming a person"][0])[2][1] == "names_person"
    assert latest_request(CASES["yes to an offer"][0])[2][1] == "accepts_offer"


def test_a_yes_with_no_offer_in_view_is_told_apart_from_a_message_that_asks_for_no_one():
    # D37 try 3: the agent offered a person in words the check did not read, and then told the customer that their
    # yes was not enough. A yes the check cannot pair with an offer gets its own reason, so the agent can ask again.
    found, _, why = latest_request([("A", "Someone from the team could look at it."), ("C", "Yes, please.")])[2]
    assert found is None and why.startswith("that message is a yes, but your message just before it offers no person")
    found, _, why = latest_request([("C", "Can I cancel it?")])[2]
    assert found is None and why.startswith("that message does not ask for a person")


def test_an_earlier_request_cannot_be_quoted_for_a_later_message():
    messages = conversation([("C", "I want to talk to a person."), ("A", "Of course."), ("C", "Thanks, that's all.")])
    found, _, why = request_for_person(messages, "I want to talk to a person.")
    assert found is None and why.startswith("those words are not in the customer's latest message")


def test_words_the_customer_never_wrote_are_refused_as_such():
    found, _, why = request_for_person(conversation([("C", "Can I cancel it?")]), "I want a person")
    assert found is None and why == "customer_words are not words the customer wrote in this conversation"
