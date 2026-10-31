"""Which items the customer's words pick out among look-alikes (refund_agent.selection; plan change log, 2026-10-23).

The cases follow the development scenarios whose customers own look-alike items (D09, D17, D31 to D34) and the
contrasts of the review of 2026-10-23: a vague reference and a named item, all items and one, a real answer and a
"thanks", the same goods in two orders, identical units of one order, and a reordered or renamed inventory."""

from datetime import date

import pytest

from refund_agent.selection import Kind, asks_customer, look_alikes_unnamed, refusal

OLIVE = Kind("o1", "Linen scarf, olive", date(2026, 10, 6), date(2026, 10, 9), ("o1-u1",))
RUST = Kind("o1", "Linen scarf, rust", date(2026, 10, 6), date(2026, 10, 9), ("o1-u2",))
GLOVES = Kind("o1", "Leather gloves", date(2026, 10, 6), date(2026, 10, 9), ("o1-u3",))
SCARVES = (OLIVE, RUST, GLOVES)  # D31 and D32

FIRST = Kind("p1", "Ceramic planter, white", date(2026, 9, 28), date(2026, 10, 1), ("p1-u1",))
SECOND = Kind("p2", "Ceramic planter, white", date(2026, 10, 5), date(2026, 10, 8), ("p2-u1",))
PLANTERS = (FIRST, SECOND)  # D33 and D34

SIZE_M = Kind("t1", "Cotton T-shirt, navy, size M", date(2026, 9, 10), date(2026, 9, 14), ("t1-u1",))
SIZE_L = Kind("t1", "Cotton T-shirt, navy, size L", date(2026, 9, 10), date(2026, 9, 14), ("t1-u2",))
SHIRTS = (SIZE_M, SIZE_L)  # D09

GLASSES = (Kind("g1", "Crystal wine glass", date(2026, 8, 28), date(2026, 9, 1), ("g1-u2", "g1-u3")),)  # D03

VAGUE_SCARF = [("customer", "Hi, I posted the linen scarf back last week. Can I have a refund?")]
VAGUE_PLANTER = [("customer", "Hello, I sent back the white ceramic planter. Can I get my money back?")]
VAGUE_SHIRT = [("customer", "Hi, I sent back the navy T-shirt. Can I get my money back?")]


def allowed(kinds, units, messages):
    return look_alikes_unnamed(kinds, units, messages) == ()


CASES = {
    # A vague reference is not a choice, whether the agent picks one item or all of them (D31, D09, D17).
    "one of two scarves, from a vague reference": (SCARVES, ["o1-u1"], VAGUE_SCARF, False),
    "both scarves, from a vague reference": (SCARVES, ["o1-u1", "o1-u2"], VAGUE_SCARF, False),
    "an item with no look-alike": (SCARVES, ["o1-u3"], VAGUE_SCARF, True),
    "one of two planters in two orders": (PLANTERS, ["p2-u1"], VAGUE_PLANTER, False),
    "one of two shirts": (SHIRTS, ["t1-u2"], VAGUE_SHIRT, False),
    # The customer's own words that tell the item apart
    "the scarf named by its colour": (SCARVES, ["o1-u1"], [*VAGUE_SCARF, ("customer", "The olive one, please.")], True),
    "the other scarf, not named": (SCARVES, ["o1-u2"], [*VAGUE_SCARF, ("customer", "The olive one, please.")], False),
    "the shirt named by its size": (SHIRTS, ["t1-u2"], [*VAGUE_SHIRT, ("customer", "The size L one.")], True),
    "an I'm is not a size M": (SHIRTS, ["t1-u1"], [*VAGUE_SHIRT, ("customer", "I'm not sure, sorry.")], False),
    "the planter named by the date it was ordered (D34)": (
        PLANTERS,
        ["p2-u1"],
        [("customer", "I sent back the white ceramic planter from the order I placed on 5 October.")],
        True,
    ),
    "the planter named by the date, month first": (PLANTERS, ["p2-u1"], [("customer", "The October 5th one.")], True),
    "the planter named by the date it arrived": (PLANTERS, ["p2-u1"], [("customer", "It came on 8 Oct.")], True),
    "the planter named by its order": (PLANTERS, ["p2-u1"], [("customer", "The one in order p2.")], True),
    "the other planter, not named": (
        PLANTERS,
        ["p1-u1"],
        [("customer", "The one from my order of 5 October.")],
        False,
    ),
    # All of them: said in so many words, or each named (D32)
    "both scarves, named as both (D32)": (
        SCARVES,
        ["o1-u1", "o1-u2"],
        [("customer", "Hi, I sent back both linen scarves, the olive one and the rust one. Please refund both.")],
        True,
    ),
    "both scarves, each named": (SCARVES, ["o1-u1", "o1-u2"], [("customer", "The olive and the rust scarf.")], True),
    "a 'that's all' is not all of them": (
        SCARVES,
        ["o1-u1", "o1-u2"],
        [*VAGUE_SCARF, ("customer", "That's all, thanks.")],
        False,
    ),
    # An answer to the agent's question about the item
    "a yes to a question that names the item": (
        SCARVES,
        ["o1-u1"],
        [*VAGUE_SCARF, ("agent", "Do you mean the olive one?"), ("customer", "Yes.")],
        True,
    ),
    "a yes to that question does not pick the other item": (
        SCARVES,
        ["o1-u2"],
        [*VAGUE_SCARF, ("agent", "Do you mean the olive one?"), ("customer", "Yes.")],
        False,
    ),
    "a thanks to a question that names nothing": (
        SCARVES,
        ["o1-u1"],
        [*VAGUE_SCARF, ("agent", "Which one would you like refunded?"), ("customer", "Thanks.")],
        False,
    ),
    "a statement that names the item is not a question": (
        SCARVES,
        ["o1-u1"],
        [*VAGUE_SCARF, ("agent", "I found the olive scarf and the rust scarf."), ("customer", "Ok.")],
        False,
    ),
    "an answer to a question asked before another message": (
        SCARVES,
        ["o1-u1"],
        [
            *VAGUE_SCARF,
            ("agent", "Do you mean the olive one?"),
            ("customer", "Hmm."),
            ("agent", "Take your time."),
            ("customer", "Ok."),
        ],
        False,
    ),
    # Identical units of one order are one kind: which unit is taken changes nothing (D03, D16).
    "one of identical units in one order": (GLASSES, ["g1-u2"], [("customer", "Refund the glass I sent back.")], True),
    # A look-alike the customer names, for which the agent proposes the other one (the review's requested vs eligible)
    "the named item swapped for its look-alike": (
        SCARVES,
        ["o1-u1"],
        [("customer", "Please refund the rust scarf.")],
        False,
    ),
    # The review after the selection check (2026-10-23): five counterexamples, each with its positive opposite.
    # A word excluded by "not", "keep", "except" or "instead of" names nothing.
    "a negated mention": (SCARVES, ["o1-u1"], [("customer", "Not the olive one. Please refund the rust one.")], False),
    "the other item after a negated mention": (
        SCARVES,
        ["o1-u2"],
        [("customer", "Not the olive one. Please refund the rust one.")],
        True,
    ),
    # The customer's latest word about an item counts, and "only" or "just" leaves out the others.
    "an item the customer changed their mind about": (
        SCARVES,
        ["o1-u1"],
        [
            ("customer", "Please refund the olive scarf."),
            ("agent", "Sure."),
            ("customer", "Actually, keep the olive one. Refund only the rust scarf."),
        ],
        False,
    ),
    "the item chosen after the change": (
        SCARVES,
        ["o1-u2"],
        [
            ("customer", "Please refund the olive scarf."),
            ("agent", "Sure."),
            ("customer", "Actually, keep the olive one. Refund only the rust scarf."),
        ],
        True,
    ),
    "an item left out by 'only' after both were named": (
        SCARVES,
        ["o1-u1"],
        [
            ("customer", "Please refund the olive and the rust scarf."),
            ("agent", "Sure."),
            ("customer", "Actually, refund only the rust scarf."),
        ],
        False,
    ),
    "the item kept by 'only' after both were named": (
        SCARVES,
        ["o1-u2"],
        [
            ("customer", "Please refund the olive and the rust scarf."),
            ("agent", "Sure."),
            ("customer", "Actually, refund only the rust scarf."),
        ],
        True,
    ),
    "an item added in a later message": (
        SCARVES,
        ["o1-u1", "o1-u2"],
        [("customer", "I returned the olive scarf."), ("agent", "Noted."), ("customer", "And the rust one too.")],
        True,
    ),
    "just one size, the other left out": (
        SHIRTS,
        ["t1-u1"],
        [*VAGUE_SHIRT, ("agent", "Size M or size L?"), ("customer", "Just the size L, please.")],
        False,
    ),
    "the size named with 'only', 'not both'": (
        SHIRTS,
        ["t1-u2"],
        [*VAGUE_SHIRT, ("customer", "I want a refund for the size L shirt only, not both shirts.")],
        True,
    ),
    "a refusal and the choice split by a dash": (
        SHIRTS,
        ["t1-u2"],
        [*VAGUE_SHIRT, ("customer", "That's not what I want—I'm only requesting a refund for the size L shirt.")],
        True,
    ),
    # A number is "all of them" only with the items it counts.
    "a number that counts weeks": (
        SCARVES,
        ["o1-u1", "o1-u2"],
        [("customer", "I sent the scarf back two weeks ago. Please refund it.")],
        False,
    ),
    "a number that counts the scarves": (
        SCARVES,
        ["o1-u1", "o1-u2"],
        [("customer", "I sent back the two scarves two weeks ago. Please refund them.")],
        True,
    ),
    "all of them": (SCARVES, ["o1-u1", "o1-u2"], [*VAGUE_SCARF, ("customer", "Please refund all of them.")], True),
    # An answer resolves the agent's question only when it is a yes to a question that named this item alone.
    "a no to a question that names the item": (
        SCARVES,
        ["o1-u1"],
        [*VAGUE_SCARF, ("agent", "Do you mean the olive one?"), ("customer", "No.")],
        False,
    ),
    "a thanks to a question that names the item": (
        SCARVES,
        ["o1-u1"],
        [*VAGUE_SCARF, ("agent", "Do you mean the olive one?"), ("customer", "Thanks.")],
        False,
    ),
    "a no, then the other item": (
        SCARVES,
        ["o1-u2"],
        [*VAGUE_SCARF, ("agent", "Do you mean the olive one?"), ("customer", "No, the rust one.")],
        True,
    ),
    "a yes to a question that names both": (
        SCARVES,
        ["o1-u1"],
        [*VAGUE_SCARF, ("agent", "The olive or the rust one?"), ("customer", "Yes.")],
        False,
    ),
    "the positive control of the review": (
        SCARVES,
        ["o1-u1"],
        [("customer", "Please refund only the olive scarf.")],
        True,
    ),
}


# v1.3 repair 2 (plan change log, 2026-10-31): two products with different names that the customer's words fit equally.
# In H281 of v1.2's final run Luna proposed both black accessories for "the black camera accessory" in 6 of 6 tries
# (A and C); the check grouped only one product family, so it never looked. The repair must also let a clear choice
# through: "the wrist strap", or "both" when the customer says both.

STRAP = Kind("c1", "Black camera wrist strap", date(2026, 10, 1), date(2026, 10, 5), ("c1-u1",))
POUCH = Kind("c1", "Black camera pouch", date(2026, 10, 1), date(2026, 10, 5), ("c1-u2",))
LENS = Kind("c1", "Gray camera lens case", date(2026, 10, 1), date(2026, 10, 5), ("c1-u3",))
CAMERA = (STRAP, POUCH, LENS)  # H281
VAGUE_CAMERA = [("customer", "Please refund the black camera accessory I returned. Is the price after the discount?")]
ASKED = [*VAGUE_CAMERA, ("agent", "Which one would you like refunded: the wrist strap or the pouch?")]

KETTLE = Kind("k1", "Electric kettle, black", date(2026, 10, 20), date(2026, 10, 24), ("k1-u1",))
DESCALER = Kind("k1", "Kettle descaler", date(2026, 10, 20), date(2026, 10, 24), ("k1-u2",))
KITCHEN = (KETTLE, DESCALER)  # S06
RED_KETTLE = [("customer", "Hello! I returned the red kettle, it was too loud. Could you refund it?")]

BIN = Kind("s1", "Felt storage bin", date(2026, 10, 25), date(2026, 10, 31), ("s1-u1",))
BASKET = Kind("s1", "Wicker storage basket", date(2026, 10, 25), date(2026, 10, 31), ("s1-u2",))
CRATE = Kind("s1", "Wooden storage crate", date(2026, 10, 25), date(2026, 10, 31), ("s1-u3",))
STORAGE = (BIN, BASKET, CRATE)  # H245

MUG = Kind("m1", "Ceramic mug", date(2026, 10, 2), date(2026, 10, 6), ("m1-u1",))
PLATE = Kind("m1", "Ceramic plate", date(2026, 10, 2), date(2026, 10, 6), ("m1-u2",))

CASES.update(
    {
        "one of two products the words fit equally (H281)": (CAMERA, ["c1-u1"], VAGUE_CAMERA, False),
        "both products the words fit equally (H281)": (CAMERA, ["c1-u1", "c1-u2"], VAGUE_CAMERA, False),
        "the product named after the question": (
            CAMERA,
            ["c1-u1"],
            [*ASKED, ("customer", "The wrist strap, please.")],
            True,
        ),
        "the other product, after the first was named": (
            CAMERA,
            ["c1-u2"],
            [*ASKED, ("customer", "The wrist strap, please.")],
            False,
        ),
        "both, after the first was named": (
            CAMERA,
            ["c1-u1", "c1-u2"],
            [*ASKED, ("customer", "The wrist strap, please.")],
            False,
        ),
        "both, when the customer says both": (
            CAMERA,
            ["c1-u1", "c1-u2"],
            [("customer", "Please refund both black camera accessories I returned.")],
            True,
        ),
        "the product named from the start": (
            CAMERA,
            ["c1-u2"],
            [("customer", "Please refund the black camera pouch I returned.")],
            True,
        ),
        "a word that fits only one of them": (CAMERA, ["c1-u3"], [("customer", "Refund the gray case.")], True),
        "the kettle, named by its noun though the colour is wrong (S06)": (KITCHEN, ["k1-u1"], RED_KETTLE, True),
        "the kettle and the descaler, for the kettle (S06)": (KITCHEN, ["k1-u1", "k1-u2"], RED_KETTLE, False),
        "the descaler, for the kettle (S06)": (KITCHEN, ["k1-u2"], RED_KETTLE, False),
        "two products named, beside another of the same kind (H245)": (
            STORAGE,
            ["s1-u1", "s1-u2"],
            [("customer", "Refund the felt bin and wicker basket in my delivered order; I kept its crate.")],
            True,
        ),
        "a shared material is not a choice": (
            (MUG, PLATE),
            ["m1-u1"],
            [("customer", "I sent back the ceramic one. Can I get a refund?")],
            False,
        ),
        "the material and the noun": (
            (MUG, PLATE),
            ["m1-u1"],
            [("customer", "I sent back the ceramic mug. Can I get a refund?")],
            True,
        ),
        "the descaler, named with the kettle in its name": (
            KITCHEN,
            ["k1-u2"],
            [("customer", "I returned the kettle descaler. Refund it, please.")],
            True,
        ),
        "the kettle, when the customer named the kettle descaler": (
            KITCHEN,
            ["k1-u1"],
            [("customer", "I returned the kettle descaler. Refund it, please.")],
            False,
        ),
        "a product named in the singular, its name in the plural": (
            (
                Kind("g2", "Glass coasters", date(2026, 10, 2), date(2026, 10, 6), ("g2-u1",)),
                Kind("g2", "Glass vase", date(2026, 10, 2), date(2026, 10, 6), ("g2-u2",)),
            ),
            ["g2-u1"],
            [("customer", "I returned the glass coaster. Can I get a refund?")],
            True,
        ),
        "a word such as 'the' in two names is not a choice": (
            (
                Kind("n1", "The Original rain jacket", date(2026, 10, 2), date(2026, 10, 6), ("n1-u1",)),
                Kind("n1", "The Classic tote", date(2026, 10, 2), date(2026, 10, 6), ("n1-u2",)),
            ),
            ["n1-u1"],
            [("customer", "Refund the item I returned, please.")],
            True,
        ),
        # Exclusions and a changed choice (release brief of 2026-10-31, checked with free probes): a word the customer
        # said of a product in "not the pouch" or "instead of the strap" does not name it.
        "the strap, not the pouch": (
            CAMERA,
            ["c1-u1"],
            [*ASKED, ("customer", "The wrist strap, not the pouch.")],
            True,
        ),
        "the pouch, after the customer said not the pouch": (
            CAMERA,
            ["c1-u2"],
            [*ASKED, ("customer", "The wrist strap, not the pouch.")],
            False,
        ),
        "the pouch, after a changed choice": (
            CAMERA,
            ["c1-u2"],
            [*ASKED, ("customer", "The wrist strap."), ("customer", "Actually, the pouch instead of the strap.")],
            True,
        ),
        "the strap, after a changed choice": (
            CAMERA,
            ["c1-u1"],
            [*ASKED, ("customer", "The wrist strap."), ("customer", "Actually, the pouch instead of the strap.")],
            False,
        ),
        "a product the customer's 'both' did not describe": (
            CAMERA,
            ["c1-u1", "c1-u2", "c1-u3"],
            [("customer", "Please refund both black camera accessories I returned.")],
            False,
        ),
        # A known limit, kept on purpose: words that name nothing of any product leave the choice to the agent's
        # question, as before, or every customer with several orders would be stopped.
        "words that name no product": ((MUG, PLATE), ["m1-u1"], [("customer", "Refund what I sent back.")], True),
    }
)


@pytest.mark.parametrize("case", sorted(CASES))
def test_which_items_the_customers_words_pick_out(case):
    kinds, units, messages, holds = CASES[case]
    assert allowed(kinds, units, messages) is holds


def test_the_order_and_names_of_the_inventory_do_not_change_the_decision():
    renamed = tuple(
        Kind(k.order_id.upper() + "x", k.product, k.placed, k.delivered, tuple(u + "x" for u in k.unit_ids))
        for k in reversed(PLANTERS)
    )
    said = [("customer", "The one from my order of 5 October.")]
    assert allowed(renamed, ["p2-u1x"], said) and not allowed(renamed, ["p1-u1x"], said)
    assert allowed(PLANTERS, ["p2-u1"], said) and not allowed(PLANTERS, ["p1-u1"], said)


def test_the_unnamed_look_alikes_are_the_whole_group():
    assert look_alikes_unnamed(SCARVES, ["o1-u1"], VAGUE_SCARF) == (OLIVE, RUST)


def test_the_refusal_lists_each_look_alike_with_what_tells_it_apart():
    text = refusal(PLANTERS)
    assert "Ceramic planter, white (order p1, placed 28 September, unit p1-u1)" in text
    assert "Ceramic planter, white (order p2, placed 5 October, unit p2-u1)" in text
    assert "wait for the answer" in text


QUESTIONS = {
    "Which scarf would you like refunded?": True,
    "I found two scarves, olive and rust. Which one do you mean? (refund-policy/v2/amount)": True,
    "Let me check your orders.": False,
    "You asked 'Where is my order?' I will check its status.": False,
    'You asked "Where is my order?" I will check its status.': False,
    "You asked “Where is my order?” I will check its status.": False,
    # An instruction asks for input without a question mark: the graph lets it through, and the selection check stops
    # a proposal made before the customer's answer (tests/acceptance/test_agent_graph.py).
    "Please choose the olive or the rust scarf.": False,
}


@pytest.mark.parametrize("text", sorted(QUESTIONS))
def test_a_message_asks_the_customer_when_it_has_a_question_mark_outside_quotations(text):
    assert asks_customer(text) is QUESTIONS[text]
