"""What counts as the customer's request for a person, in words (refunds.request_for_person; plan change log,
2026-10-22). The cases come in pairs that differ in the one thing that decides: a request and a refusal, an offer and
a question, a yes and a no, a current request and a withdrawn one. Code cannot read consent; these are the cases a
check of words must still get right, and the customer's button stays the request no reading can doubt."""

import pytest

from refund_agent.refunds import request_for_person

OFFER = "Cancelling is outside this process. Would you like me to connect you with a staff member?"

CASES = {
    # A request in the customer's own words
    "a request naming a person": ([("C", "I'd like to talk to someone from your team, please.")], True),
    "a person wanted, an assistant not": ([("C", "I want to speak to a person, please, not an assistant.")], True),
    "a person declined": ([("C", "I don't want to talk to a person, just refund it.")], False),
    "a question with no person in it": ([("C", "My rice cooker is on its way. Can I cancel it?")], False),
    "a request withdrawn in the same message": ([("C", "Can I talk to a person? Actually, never mind.")], False),
    "a request withdrawn later": (
        [("C", "I want to talk to a person."), ("A", "Of course."), ("C", "Never mind, I don't need anyone now.")],
        False,
    ),
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
    "no to an offer": ([("C", "Can I cancel it?"), ("A", OFFER), ("C", "No, thanks.")], False),
    "a yes that declines": ([("C", "Can I cancel it?"), ("A", OFFER), ("C", "Yes, but not now.")], False),
    "yes to a question that names staff and offers no one": (
        [
            ("C", "I sent back the lamp."),
            ("A", "A staff member approves refunds. Did you get my last message?"),
            ("C", "Yes."),
        ],
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


def conversation(turns):
    return [(f"m{n}", "customer" if who == "C" else "agent", words) for n, (who, words) in enumerate(turns)]


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_request_for_a_person_in_words(case):
    turns, holds = CASES[case]
    messages = conversation(turns)
    latest = [m for m in messages if m[1] == "customer"][-1]
    found, why = request_for_person(messages, latest[2])  # the agent quotes the whole latest message
    assert (found is not None) == holds, why
    assert found in (None, latest[0])


def test_an_earlier_request_cannot_be_quoted_for_a_later_message():
    messages = conversation([("C", "I want to talk to a person."), ("A", "Of course."), ("C", "Thanks, that's all.")])
    found, why = request_for_person(messages, "I want to talk to a person.")
    assert found is None and why.startswith("those words are not in the customer's latest message")


def test_words_the_customer_never_wrote_are_refused_as_such():
    found, why = request_for_person(conversation([("C", "Can I cancel it?")]), "I want a person")
    assert found is None and why == "customer_words are not words the customer wrote in this conversation"
