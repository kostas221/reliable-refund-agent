"""What counts as the customer saying that units were already sent back (refunds.claim_of_sending; the owner's
rehearsal, 2026-11-07, finding 5). A `return_disputed` handoff hands the conversation to a person, which the
assistant cannot undo; in the rehearsal it rested on "i send them back", after the customer had written "If I send them
next Monday". The cases come in pairs that differ in the one thing that decides. The check refuses words that plainly
claim no sending; whether a claim is true stays the staff member's to check, and the customer's button stays the way
to a person that no reading can doubt."""

import pytest

from refund_agent.refunds import claim_of_sending

ASKED = (  # the agent's question in the rehearsal (runs/live-20261107T133258Z), kept exactly
    "Do you mean you’ve already sent the trail running shoes back, or that you want a refund once they arrive? The "
    "shop’s records currently don’t show them as received, and they must arrive before a refund can be requested "
    "(refund-policy/v2/return)."
)
PLAIN_QUESTION = "Have you already sent the shoes back?"

CASES = {
    # The rehearsal, kept exactly
    "the rehearsal's conversation": (
        [
            ("C", "f I send them next Monday, can I still get a refund?"),
            ("A", "For your trail running shoes, sending them Monday does not guarantee a refund."),
            ("C", "the trail running shoes they arrive?i refund them"),
            ("A", ASKED),
            ("C", "i send them back"),
        ],
        False,
    ),
    # A claim in the customer's own words, and the same words that claim nothing
    "sent, past": ([("C", "Hi, I sent the duvet set back over a week ago. Why haven't I got my refund yet?")], True),
    "not sent yet": ([("C", "I haven't sent the duvet set back yet. Can I still get a refund?")], False),
    "posted": ([("C", "I posted them back last Monday, with tracking.")], True),
    "will post": ([("C", "I will post them back on Monday.")], False),
    "returned": ([("C", "I've returned the shoes already.")], True),
    "returned, if": ([("C", "If I returned the shoes today, would I get the money?")], False),
    "dropped off": ([("C", "I dropped them off at the post office on Friday.")], True),
    "once sent": ([("C", "Once I've sent them, can I get a refund?")], False),
    "on its way back": ([("C", "The parcel is on its way back to you.")], True),
    "a claim beside a negation in another clause": ([("C", "I sent the scarf back, not the gloves.")], True),
    "a claim earlier in the conversation": (
        [("C", "I mailed the lamp back two weeks ago."), ("A", "Let me check."), ("C", "Any news?")],
        True,
    ),
    # Who sent what, and a question against a statement (review of 2026-11-08: the first two were accepted)
    "a question about a future return": ([("C", "Can the shoes be returned next week?")], False),
    "the shop's shipping to the customer": ([("C", "You sent the wrong shoes.")], False),
    "the shop's shipping, named": ([("C", "The shop sent me the wrong colour.")], False),
    "the shop's shipping, after another verb": ([("C", "I think you sent the wrong size.")], False),
    "a question whether they were returned": ([("C", "Were the shoes returned?")], False),
    "a passive statement": ([("C", "The shoes were sent back last week.")], True),
    "a passive statement with it": ([("C", "It was returned on Monday.")], True),
    "a passive statement about the shop's shipping": ([("C", "The wrong shoes were sent to me.")], False),
    "the customer's own sending, inside a question": ([("C", "Have you received the shoes I sent?")], True),
    "no subject, a statement": ([("C", "Already sent them back last week.")], True),
    "no subject, a statement before a question": ([("C", "Sent it back on Monday, why no refund yet?")], True),
    # A yes to the agent's question whether they were sent
    "a yes to a plain question": ([("A", PLAIN_QUESTION), ("C", "Yes.")], True),
    "a no to a plain question": ([("A", PLAIN_QUESTION), ("C", "No, not yet.")], False),
    "a yes to a question about something else": (
        [("A", "Would you like a refund for the olive scarf?"), ("C", "Yes, please.")],
        False,
    ),
}


@pytest.mark.parametrize(("messages", "claims"), CASES.values(), ids=CASES.keys())
def test_a_claim_of_sending_is_read_from_the_customers_words(messages, claims):
    numbered = [(f"m{n}", "customer" if who == "C" else "agent", said) for n, (who, said) in enumerate(messages)]
    found = claim_of_sending(numbered)
    assert (found.message_id is not None) is claims, found.unmet
    if not claims:
        assert found.unmet


def test_a_claim_names_the_message_it_rests_on_and_how():
    messages = [("m0", "customer", "I posted them back last Monday."), ("m1", "agent", "Thanks.")]
    assert claim_of_sending(messages)[:2] == ("m0", "claims_sent")
    asked = [("m0", "agent", PLAIN_QUESTION), ("m1", "customer", "Yes, last week.")]
    assert claim_of_sending(asked)[:2] == ("m1", "answers_question")


# Known limits of a check of words, kept so that a change in them is seen.
LIMITS = {
    # "send" with a time in the past, in English that is not the customer's first language, is read as no claim:
    # the agent asks again, and the customer's next words or the button decide.
    "present tense with a past time": ([("C", "I send them back last week.")], False),
    # Someone else as the sender is read as no claim: the agent asks, and the customer's next words decide.
    "another person sent them": ([("C", "My husband sent them back on Friday.")], False),
    # A later withdrawal is not read: any claim in the conversation counts.
    "a claim withdrawn later": (
        [("C", "I sent them back."), ("A", "Thanks."), ("C", "Sorry, I haven't sent them yet.")],
        True,
    ),
}


@pytest.mark.parametrize(("messages", "claims"), LIMITS.values(), ids=LIMITS.keys())
def test_the_known_limits_of_the_check(messages, claims):
    numbered = [(f"m{n}", "customer" if who == "C" else "agent", said) for n, (who, said) in enumerate(messages)]
    assert (claim_of_sending(numbered).message_id is not None) is claims
