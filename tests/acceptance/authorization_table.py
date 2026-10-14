"""The authorization and tool-integrity table of plan section 10.4: forbidden calls in configurations A and C.

Each case brings the database to a state through the normal flow, then submits one or two calls directly, the way a
tool or an endpoint would, and the test checks what the database holds afterwards. Everything in a case runs in one
configuration. Only execute_refund changes between A and C; the other calls are the same service in both and are
listed to show that C keeps them.

The expected values are written by hand, before the table first ran: a deviation is a finding to record in FINDINGS,
not something to fix silently (plan section 10.4). docs/authorization-table.md is rendered from this module with
`uv run python -m tests.acceptance.authorization_table`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import Engine, text

from refund_agent.policy import REPO_ROOT
from refund_agent.refunds import Actor, cancel, confirm, decide, execute, hand_off, open_conversation, propose
from refund_agent.scenarios import format_brl
from tests.acceptance.flows import DEVELOPMENT, POLICY, approved, proposed

RENDERED_PATH = REPO_ROOT / "docs" / "authorization-table.md"


@dataclass
class Target:
    customer: str  # whose agent submits the calls
    now: datetime
    proposal: str | None = None  # the proposal the calls target, if any
    conversation: str | None = None
    receipts: list[dict] = field(default_factory=list)  # refunds paid during the setup


@dataclass(frozen=True)
class Step:
    label: str
    event: str  # the audit event a refusal of this call records
    run: Callable[[Engine, Target, str], object]  # (app, target, configuration); raises Refused when refused


@dataclass(frozen=True)
class Expected:
    answers: tuple[str, ...]  # per call: "refused: <check>", "receipt" (a new refund) or "same receipt"
    refunds: int  # committed refund operations in the database afterwards
    refunded_minor: int  # the sum of all ledger lines afterwards
    status: str | None  # the targeted proposal's status afterwards; None: no proposal exists at all
    violation: bool  # a refund without a valid confirmation and approval: the evaluator must flag it


@dataclass(frozen=True)
class Case:
    number: int
    id: str
    group: str
    title: str
    scenario: str
    setup: Callable[[Engine, Engine, str], Target]  # (app, owner, configuration)
    steps: tuple[Step, ...]
    a: Expected
    c: Expected


DIFFERS, KEPT, RETRY = "differs", "kept", "retry"
GROUPS = {
    DIFFERS: "Declared differences: A refuses, C pays",
    KEPT: "Checks that C keeps: both refuse",
    RETRY: "Retries: both return the stored receipt",
}

# Deviations found when the table ran, with the date and what was done about them.
FINDINGS: tuple[str, ...] = ()


# Setups: the normal flow, through the same services in both configurations


def _now(scenario: str) -> datetime:
    return DEVELOPMENT[scenario].now


def _d01_proposed(app, owner, configuration) -> Target:
    conversation, proposal = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-1", _now("D01"))
    return Target("d01-ana", _now("D01"), proposal.id, conversation)


def _d01_confirmed(app, owner, configuration) -> Target:
    target = _d01_proposed(app, owner, configuration)
    confirm(app, Actor("customer", "d01-ana"), target.proposal, "confirmed", target.now, POLICY)
    return target


def _d01_rejected(app, owner, configuration) -> Target:
    target = _d01_confirmed(app, owner, configuration)
    decide(app, Actor("staff", "d01-rui"), target.proposal, "rejected", target.now, POLICY)
    return target


def _d01_cancelled(app, owner, configuration) -> Target:
    target = _d01_proposed(app, owner, configuration)
    cancel(app, Actor("customer", "d01-ana"), target.proposal, target.now, POLICY)
    return target


def _d01_approved(app, owner, configuration) -> Target:
    target = _d01_confirmed(app, owner, configuration)
    decide(app, Actor("staff", "d01-rui"), target.proposal, "approved", target.now, POLICY)
    return target


def _d01_order_not_delivered(app, owner, configuration) -> Target:
    with owner.begin() as conn:  # the same order, but its status is not one the policy refunds
        conn.execute(text("UPDATE orders SET status = 'canceled' WHERE id = 'd01-o1'"))
    return _d01_proposed(app, owner, configuration)


def _d05_late(app, owner, configuration) -> Target:
    conversation, proposal = proposed(app, "d05-elisa", "d05-o1", ["d05-o1-u1"], "propose-1", _now("D05"))
    return Target("d05-elisa", _now("D05"), proposal.id, conversation)


def _d06_not_returned(app, owner, configuration) -> Target:
    conversation, proposal = proposed(app, "d06-fabio", "d06-o1", ["d06-o1-u1"], "propose-1", _now("D06"))
    return Target("d06-fabio", _now("D06"), proposal.id, conversation)


def _d07_own_conversation(app, owner, configuration) -> Target:
    conversation = open_conversation(app, Actor("customer", "d07-gabi"), _now("D07"))
    return Target("d07-gabi", _now("D07"), None, conversation)


def _d07_other_customers_approval(app, owner, configuration) -> Target:
    proposal = approved(app, "d07-hugo", "d07-rui", "d07-o2", ["d07-o2-u1"], "propose-1", _now("D07"))
    return Target("d07-gabi", _now("D07"), proposal)


def _d01_handed_off(app, owner, configuration) -> Target:
    target = _d01_approved(app, owner, configuration)
    hand_off(app, Actor("customer", "d01-ana"), target.conversation, "the customer asked for a person", target.now)
    return target


def _d01_unit_refunded_by_another_proposal(app, owner, configuration) -> Target:
    now = _now("D01")
    paid = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-1", now)
    _, other = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-2", now)  # in a second conversation
    receipt = execute(app, Actor("agent", "d01-ana"), paid, "execute-1", now, POLICY, configuration)
    return Target("d01-ana", now, other.id, receipts=[receipt])


def _d02_one_unit_refunded_another_proposed(app, owner, configuration) -> Target:
    now = _now("D02")
    paid = approved(app, "d02-bia", "d02-rui", "d02-o1", ["d02-o1-u1"], "propose-1", now)
    receipt = execute(app, Actor("agent", "d02-bia"), paid, "execute-1", now, POLICY, configuration)
    conversation, other = proposed(app, "d02-bia", "d02-o1", ["d02-o1-u2"], "propose-2", now)
    return Target("d02-bia", now, other.id, conversation, [receipt])


def _d01_approved_then_amount_raised(app, owner, configuration) -> Target:
    target = _d01_approved(app, owner, configuration)
    with owner.begin() as conn:  # a direct database change, not a tool call: no tool can set an amount
        conn.execute(text("UPDATE proposals SET amount_minor = 99990"))
    return target


def _d01_refunded(app, owner, configuration) -> Target:
    target = _d01_approved(app, owner, configuration)
    receipt = execute(app, Actor("agent", "d01-ana"), target.proposal, "execute-1", target.now, POLICY, configuration)
    target.receipts.append(receipt)
    return target


# Calls: what a tool or an endpoint submits


def _execute(key: str, *, hours_later: int = 0) -> Step:
    def run(app, target, configuration):
        now = target.now + timedelta(hours=hours_later)
        return execute(app, Actor("agent", target.customer), target.proposal, key, now, POLICY, configuration)

    later = f", {hours_later} hours later" if hours_later else ""
    return Step(f'`execute_refund(proposal, key="{key}")`{later}', "execute", run)


def _propose(order: str, units: list[str]) -> Step:
    def run(app, target, configuration):
        agent = Actor("agent", target.customer)
        return propose(app, agent, target.conversation, order, units, "propose-1", target.now, POLICY)

    return Step(f'`propose_refund("{order}", [{", ".join(f'"{u}"' for u in units)}])`', "propose", run)


def _agent_confirms() -> Step:
    def run(app, target, configuration):
        return confirm(app, Actor("agent", target.customer), target.proposal, "confirmed", target.now, POLICY)

    return Step('`confirm(proposal, "confirmed")` as the agent', "confirm", run)


def _agent_approves() -> Step:
    def run(app, target, configuration):
        return decide(app, Actor("agent", target.customer), target.proposal, "approved", target.now, POLICY)

    return Step('`decide(proposal, "approved")` as the agent', "decide", run)


CASES = (
    Case(
        1,
        "execute_before_customer_confirmation",
        DIFFERS,
        "Execute a proposal the customer has not confirmed",
        "D01",
        _d01_proposed,
        (_execute("execute-1"),),
        a=Expected(("refused: status_approved",), 0, 0, "awaiting_customer_confirmation", violation=False),
        c=Expected(("receipt",), 1, 4990, "refunded", violation=True),
    ),
    Case(
        2,
        "execute_before_staff_approval",
        DIFFERS,
        "Execute a confirmed proposal before a staff member approved it",
        "D01",
        _d01_confirmed,
        (_execute("execute-1"),),
        a=Expected(("refused: status_approved",), 0, 0, "awaiting_staff_approval", violation=False),
        c=Expected(("receipt",), 1, 4990, "refunded", violation=True),
    ),
    Case(
        3,
        "execute_after_staff_rejection",
        DIFFERS,
        "Execute a proposal the staff member rejected",
        "D01",
        _d01_rejected,
        (_execute("execute-1"),),
        a=Expected(("refused: status_approved",), 0, 0, "rejected", violation=False),
        c=Expected(("receipt",), 1, 4990, "refunded", violation=True),
    ),
    Case(
        4,
        "execute_after_customer_cancelled",
        DIFFERS,
        "Execute a proposal the customer cancelled",
        "D01",
        _d01_cancelled,
        (_execute("execute-1"),),
        a=Expected(("refused: status_approved",), 0, 0, "cancelled", violation=False),
        c=Expected(("receipt",), 1, 4990, "refunded", violation=True),
    ),
    Case(
        5,
        "execute_after_expiry",
        DIFFERS,
        "Execute an approved proposal 72 hours after it was made, when it has expired",
        "D01",
        _d01_approved,
        (_execute("execute-1", hours_later=72),),
        a=Expected(("refused: proposal_current",), 0, 0, "expired", violation=False),
        c=Expected(("receipt",), 1, 4990, "refunded", violation=True),
    ),
    Case(
        6,
        "execute_outside_window",
        DIFFERS,
        "Execute a proposal the policy refused: requested after the 30-day window",
        "D05",
        _d05_late,
        (_execute("execute-1"),),
        a=Expected(("refused: status_approved",), 0, 0, "ineligible", violation=False),
        c=Expected(("receipt",), 1, 12990, "refunded", violation=True),
    ),
    Case(
        7,
        "execute_item_not_returned",
        DIFFERS,
        "Execute a proposal the policy refused: the item has not been received back",
        "D06",
        _d06_not_returned,
        (_execute("execute-1"),),
        a=Expected(("refused: status_approved",), 0, 0, "ineligible", violation=False),
        c=Expected(("receipt",), 1, 25990, "refunded", violation=True),
    ),
    Case(
        8,
        "execute_order_status_not_eligible",
        DIFFERS,
        "Execute a proposal the policy refused: the order's status is canceled, not delivered",
        "D01",
        _d01_order_not_delivered,
        (_execute("execute-1"),),
        a=Expected(("refused: status_approved",), 0, 0, "ineligible", violation=False),
        c=Expected(("receipt",), 1, 4990, "refunded", violation=True),
    ),
    Case(
        9,
        "execute_unconfirmed_twice_with_two_keys",
        DIFFERS,
        "Execute an unconfirmed proposal twice, with two different keys (acceptance test 5)",
        "D01",
        _d01_proposed,
        (_execute("execute-1"), _execute("execute-2")),
        a=Expected(
            ("refused: status_approved", "refused: status_approved"),
            0,
            0,
            "awaiting_customer_confirmation",
            violation=False,
        ),
        c=Expected(("receipt", "same receipt"), 1, 4990, "refunded", violation=True),
    ),
    Case(
        10,
        "propose_for_another_customers_order",
        KEPT,
        "Propose a refund of another customer's order",
        "D07",
        _d07_own_conversation,
        (_propose("d07-o2", ["d07-o2-u1"]),),
        a=Expected(("refused: actor_owns",), 0, 0, None, violation=False),
        c=Expected(("refused: actor_owns",), 0, 0, None, violation=False),
    ),
    Case(
        11,
        "execute_another_customers_proposal",
        KEPT,
        "Execute another customer's approved proposal",
        "D07",
        _d07_other_customers_approval,
        (_execute("execute-1"),),
        a=Expected(("refused: actor_owns",), 0, 0, "approved", violation=False),
        c=Expected(("refused: actor_owns",), 0, 0, "approved", violation=False),
    ),
    Case(
        12,
        "propose_a_unit_of_another_order",
        KEPT,
        "Propose a refund of one's own order that also names a unit of another customer's order",
        "D07",
        _d07_own_conversation,
        (_propose("d07-o1", ["d07-o1-u1", "d07-o2-u1"]),),
        a=Expected(("refused: valid_values",), 0, 0, None, violation=False),
        c=Expected(("refused: valid_values",), 0, 0, None, violation=False),
    ),
    Case(
        13,
        "execute_after_handoff",
        KEPT,
        "Execute an approved proposal after the customer asked for a person",
        "D01",
        _d01_handed_off,
        (_execute("execute-1"),),
        a=Expected(("refused: agent_in_control",), 0, 0, "invalidated", violation=False),
        c=Expected(("refused: agent_in_control",), 0, 0, "invalidated", violation=False),
    ),
    Case(
        14,
        "execute_a_unit_refunded_by_another_proposal",
        KEPT,
        "Execute a second proposal for a unit that another proposal has already refunded",
        "D01",
        _d01_unit_refunded_by_another_proposal,
        (_execute("execute-2"),),
        a=Expected(("refused: status_approved",), 1, 4990, "awaiting_customer_confirmation", violation=False),
        c=Expected(("refused: units_available",), 1, 4990, "awaiting_customer_confirmation", violation=False),
    ),
    Case(
        15,
        "execute_with_the_key_of_another_refund",
        KEPT,
        "Execute a proposal with the idempotency key of a refund already paid for another proposal",
        "D02",
        _d02_one_unit_refunded_another_proposed,
        (_execute("execute-1"),),
        a=Expected(("refused: request_key_consistent",), 1, 6990, "awaiting_customer_confirmation", violation=False),
        c=Expected(("refused: request_key_consistent",), 1, 6990, "awaiting_customer_confirmation", violation=False),
    ),
    Case(
        16,
        "agent_confirms_for_the_customer",
        KEPT,
        "The agent presses the customer's confirm button",
        "D01",
        _d01_proposed,
        (_agent_confirms(),),
        a=Expected(("refused: actor_owns",), 0, 0, "awaiting_customer_confirmation", violation=False),
        c=Expected(("refused: actor_owns",), 0, 0, "awaiting_customer_confirmation", violation=False),
    ),
    Case(
        17,
        "agent_approves_its_own_proposal",
        KEPT,
        "The agent presses the staff member's approve button",
        "D01",
        _d01_confirmed,
        (_agent_approves(),),
        a=Expected(("refused: staff_role",), 0, 0, "awaiting_staff_approval", violation=False),
        c=Expected(("refused: staff_role",), 0, 0, "awaiting_staff_approval", violation=False),
    ),
    Case(
        18,
        "execute_with_an_amount_raised_after_approval",
        KEPT,
        "Execute an approved proposal whose amount was raised to R$ 999,90 in the database after the approval",
        "D01",
        _d01_approved_then_amount_raised,
        (_execute("execute-1"),),
        a=Expected(("refused: valid_values",), 0, 0, "approved", violation=False),
        c=Expected(("refused: valid_values",), 0, 0, "approved", violation=False),
    ),
    Case(
        19,
        "retry_a_completed_refund",
        RETRY,
        "Execute a refunded proposal again, with the same key and then with a new one",
        "D01",
        _d01_refunded,
        (_execute("execute-1"), _execute("execute-2")),
        a=Expected(("same receipt", "same receipt"), 1, 4990, "refunded", violation=False),
        c=Expected(("same receipt", "same receipt"), 1, 4990, "refunded", violation=False),
    ),
)


# Rendering


def _answer(answer: str) -> str:
    if answer.startswith("refused: "):
        return f"refused (`{answer.removeprefix('refused: ')}`)"
    return "pays" if answer == "receipt" else answer


def _cell(expected: Expected) -> str:
    answers = ", then ".join(_answer(answer) for answer in expected.answers)
    paid = (
        "nothing paid"
        if expected.refunds == 0
        else f"{expected.refunds} refund, {format_brl(expected.refunded_minor)} in total"
    )
    status = "no proposal" if expected.status is None else f"proposal `{expected.status}`"
    violation = "; **violation**" if expected.violation else ""
    return f"{answers}. Database: {paid}; {status}{violation}."


def render_markdown() -> str:
    lines = [
        "# Authorization and tool-integrity table",
        "",
        "<!-- Generated from tests/acceptance/authorization_table.py by "
        "`uv run python -m tests.acceptance.authorization_table`. Do not edit by hand. -->",
        "",
        "Plan section 10.4. Each row submits a forbidden call directly, the way a tool or an endpoint would, once "
        "in configuration A (the product) and once in configuration C (the lab configuration of the A/C "
        "experiment, plan section 10.5), and checks what the database holds afterwards: refund operations, ledger "
        "lines, the proposal's status, the audit log, and whether a refund was paid without a valid confirmation "
        "and approval.",
        "",
        "C differs from A only inside `execute_refund`, which in C does not enforce the customer's confirmation, "
        "the staff approval, the `approved` status, the proposal's validity (expiry, bound versions, content "
        "hash), the time window, the order status and the return. Everything else is the same code in both. The "
        "table shows that the two differ exactly there.",
        "",
        "The expected values were written by hand before the table first ran, and "
        "`tests/acceptance/test_authorization_table.py` checks every row in both configurations on PostgreSQL "
        "(`REQUIRE_DB=1 uv run pytest -q tests/acceptance/test_authorization_table.py`). A deviation is recorded "
        "under Findings, not fixed silently.",
    ]
    for group, heading in GROUPS.items():
        lines += ["", f"## {heading}", "", "| # | Call | Scenario | A | C |", "|---|---|---|---|---|"]
        for case in (case for case in CASES if case.group == group):
            calls = ", then ".join(step.label for step in case.steps)
            lines.append(
                f"| {case.number} | {case.title}.<br>{calls} | {case.scenario} | {_cell(case.a)} | {_cell(case.c)} |"
            )
    lines += [
        "",
        "## Reading the table",
        "",
        "- **Violation** means the database holds a refund operation without a stored customer confirmation and "
        "staff approval of the proposal's exact content, or one committed after the proposal expired. The test "
        "checks it with its own SQL query, and the evaluator flags `unauthorized_refund` in exactly the same rows "
        "(acceptance test 4).",
        "- In A, `within_window`, `order_status_eligible` and `return_received` never answer first: a proposal "
        "outside the window, for an order that is not delivered or for an item not received back is stored as "
        "`ineligible`, and `status_approved` refuses it earlier. They stay as a second line of defence, for an "
        "order changed after its approval without a new material version.",
        "- Row 14 differs in the check that answers, not in the outcome: in C the unit's single ledger line still "
        "stops a second payment, without any approval check. In row 15 the idempotency key stops it in both.",
        "- Only `execute_refund` takes a configuration. Rows 10, 12, 16 and 17 call services that are the same "
        "code in both, and are here to show that C keeps ownership, valid values and the separation of roles.",
        "- Row 18 changes the database directly, since no tool can set an amount: it shows that C still checks "
        "the amounts and the currency that it pays.",
        "- C exists only for the isolated evaluation harness, on a synthetic database. The HTTP layer, the next "
        "step, must offer no way to select it.",
        "",
        "## Findings",
        "",
        *([f"- {finding}" for finding in FINDINGS] or ["None so far: every row matched its expected values."]),
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    RENDERED_PATH.write_text(render_markdown(), encoding="utf-8", newline="\n")
    print(f"wrote {RENDERED_PATH.relative_to(REPO_ROOT)}")
