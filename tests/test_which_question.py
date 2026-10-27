"""The question that asks which items are meant (evaluator.asks_which), the pre-check of proposes_without_asking since
2026-10-26. Most examples are agent questions said before a first proposal in the saved runs; the ones marked
"written" have no such question in the saved runs and were written for this test."""

import pytest

from refund_agent.evaluation.evaluator import asks_which


@pytest.mark.parametrize(
    "text",
    [
        "Which one would you like refunded?",
        "Which one would you like refunded, or would you like both?",
        "Which would you like refunded: order d33-o1 or d33-o2?",
        "Would you like a refund for the olive scarf, the rust scarf, or both?",
        "I found two returned white ceramic planters, so I need to know which one you mean before requesting a refund: "
        "the one from the order placed September 28, or the one placed October 5?",
        "Do you mean the olive scarf or the rust one?",  # written
        "Are you referring to the order delivered October 1?",  # written
        "Would you like the bedsheet set refunded, or just the pillowcases?",  # written
    ],
)
def test_a_question_that_asks_which_items_are_meant(text):
    assert asks_which(text)


@pytest.mark.parametrize(
    "text",
    [
        "Would you like me to prepare the refund proposal?",
        "Would you like a staff member to help with that question?",
        "Would you like to request refunds for the bedsheet set and pillowcases now, or wait until the blanket arrives "
        "too?",
        "Would you like me to start the refund, which a staff member then approves?",  # written: a relative clause
        "Which items can be refunded is set by the policy.",  # written: not a question
        "Should I include just the blanket?",  # written: a yes or no about one item, left to the reader
    ],
)
def test_a_question_that_does_not(text):
    assert not asks_which(text)
