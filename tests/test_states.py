"""The proposal state machine keeps roles apart, has no dead ends, and C differs from A only where declared."""

import re

from refund_agent.policy import REPO_ROOT, load_policy
from refund_agent.states import (
    CHECKS,
    FINAL,
    OPEN,
    RENDERED_PATH,
    TRANSITIONS,
    Actor,
    Status,
    render_markdown,
)


def transitions(event: str) -> list:
    return [t for t in TRANSITIONS if t.event == event]


def test_final_statuses_have_no_way_out():
    for t in TRANSITIONS:
        if t.sources is not None:
            assert not t.sources & FINAL, t.event


def test_every_status_is_reachable():
    reached = {t.target for t in TRANSITIONS if t.sources is None}
    while True:
        more = {t.target for t in TRANSITIONS if t.sources and t.sources & reached} - reached
        if not more:
            break
        reached |= more
    assert reached == set(Status)


def test_every_open_proposal_can_end_without_anyone_acting():
    (expire,) = transitions("expire")
    assert expire.sources == OPEN and expire.actor is Actor.SYSTEM


def test_handoff_closes_every_open_proposal():
    (handed_off,) = transitions("handed_off")
    assert handed_off.sources == OPEN and handed_off.target is Status.INVALIDATED


def test_money_moves_only_through_execute_after_approval():
    into_refunded = [(t.event, t.sources, t.actor) for t in TRANSITIONS if t.target is Status.REFUNDED]
    assert into_refunded == [("execute", {Status.APPROVED}, Actor.AGENT)]


def test_only_the_customer_confirms_and_only_staff_decide():
    assert {t.actor for t in TRANSITIONS if t.target is Status.AWAITING_STAFF_APPROVAL} == {Actor.CUSTOMER}
    assert {t.actor for t in TRANSITIONS if t.target in {Status.APPROVED, Status.REJECTED}} == {Actor.STAFF}


def test_every_agent_write_checks_ownership_and_control():
    for t in TRANSITIONS:
        if t.actor is Actor.AGENT:
            assert {"actor_owns", "agent_in_control"} <= set(t.checks), t.event


def test_checks_are_declared_once_and_all_used():
    names = [c.name for c in CHECKS]
    assert len(names) == len(set(names))
    assert {name for t in TRANSITIONS for name in t.checks} == set(names)


def test_configuration_c_differs_exactly_where_the_plan_says():
    # Plan section 10.5: in C, execute_refund does not enforce the customer confirmation and staff approval
    # (and their validity), the time window, the eligible order status or the received return.
    lab = {c.name for c in CHECKS if c.lab_disabled}
    assert lab == {
        "status_approved",
        "customer_confirmed",
        "staff_approved",
        "proposal_current",
        "within_window",
        "order_status_eligible",
        "return_received",
    }
    (execute,) = transitions("execute")
    assert lab <= set(execute.checks)
    # Ownership, positive amounts and currency, balance and quantity, deduplication stay enforced in C.
    # agent_in_control is not part of the experiment, so it stays enforced as well.
    assert set(execute.checks) - lab == {
        "actor_owns",
        "agent_in_control",
        "request_key_consistent",
        "first_execution",
        "approval_used_once",
        "valid_values",
        "within_remaining",
    }


def test_protected_invariants_and_policy_sections_exist():
    contract = (REPO_ROOT / "docs" / "product-contract.md").read_text(encoding="utf-8")
    invariants = set(re.findall(r"^\| (INV-\d+) ", contract, flags=re.MULTILINE))
    sections = {section.id for section in load_policy().sections}
    for check in CHECKS:
        for target in check.protects:
            if target.startswith("policy:"):
                assert target.removeprefix("policy:") in sections, (check.name, target)
            else:
                assert target in invariants, (check.name, target)


def test_rendered_document_is_in_sync():
    actual = RENDERED_PATH.read_text(encoding="utf-8")
    assert actual == render_markdown(), "docs/state-machine.md is stale: run `uv run python -m refund_agent.states`"
