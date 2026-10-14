"""The hand-written authorization table agrees with the declaration of configuration C in refund_agent/states.py.

The table's expectations are written without reading states.py; this test compares the two afterwards, so a change
to the lab-disabled checks that the table does not reflect (or the reverse) fails here, without a database.
"""

from refund_agent.states import CHECKS
from tests.acceptance.authorization_table import CASES, DIFFERS, RENDERED_PATH, render_markdown

LAB_DISABLED = {check.name for check in CHECKS if check.lab_disabled}


def refused_check(answer: str) -> str | None:
    return answer.removeprefix("refused: ") if answer.startswith("refused: ") else None


def test_a_and_c_differ_only_through_the_checks_that_c_leaves_out():
    for case in CASES:
        for a, c in zip(case.a.answers, case.c.answers, strict=True):
            if refused_check(c):
                assert refused_check(c) not in LAB_DISABLED, f"row {case.number}: C refuses with a disabled check"
            if a != c:
                assert refused_check(a) in LAB_DISABLED, f"row {case.number}: A and C differ outside the lab checks"


def test_the_declared_differences_are_exactly_the_rows_where_c_pays_and_a_does_not():
    for case in CASES:
        c_pays_alone = "receipt" in case.c.answers and "receipt" not in case.a.answers
        assert c_pays_alone is (case.group == DIFFERS), f"row {case.number}"
        assert case.c.violation is c_pays_alone, f"row {case.number}"
        assert not case.a.violation, f"row {case.number}: A never ends in a violation"


def test_rows_are_numbered_in_order():
    assert [case.number for case in CASES] == list(range(1, len(CASES) + 1))
    assert len({case.id for case in CASES}) == len(CASES)


def test_rendered_document_is_in_sync():
    actual = RENDERED_PATH.read_text(encoding="utf-8")
    assert actual == render_markdown(), (
        "docs/authorization-table.md is stale: run `uv run python -m tests.acceptance.authorization_table`"
    )
