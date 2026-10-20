"""How the evaluator finds an amount in the agent's words: in the shop's notation or in English, never inside a longer
number, and, since 2026-10-20, a whole amount without its cents (the final evaluation judged "R$49" wrong for 49,00)."""

import pytest

from refund_agent.evaluation.evaluator import amount_pattern


@pytest.mark.parametrize(
    ("minor", "text"),
    [
        (4990, "a refund of R$ 49,90"),
        (4990, "BRL 49.90"),
        (129990, "R$ 1.299,90"),
        (129990, "BRL 1,299.90"),
        (4900, "your R$49 refund"),
        (4900, "R$ 49,00"),
        (4900, "BRL 49.00."),
        (4900, "R$49."),
    ],
)
def test_an_amount_is_found_as_people_write_it(minor, text):
    assert amount_pattern(minor).search(text), text


@pytest.mark.parametrize(
    ("minor", "text"),
    [
        (4990, "R$ 49"),  # cents left out of an amount that has them
        (4900, "R$ 490"),
        (4900, "R$ 149"),
        (4900, "R$ 49,50"),
        (4900, "BRL 49.5"),
        (4990, "R$ 149,90"),
    ],
)
def test_no_other_number_passes_for_it(minor, text):
    assert not amount_pattern(minor).search(text), text
