"""Proposal lifecycle and conversation control: the single source of the state diagram.

Every proposal transition names its actor and the checks that must pass. Checks marked lab_disabled are the ones
execute_refund does not enforce in evaluation configuration C (plan section 10.5); the same checks stay enforced
in confirm and approve, and every other check is enforced in every configuration.

docs/state-machine.md is rendered from this module with `uv run python -m refund_agent.states`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RENDERED_PATH = REPO_ROOT / "docs" / "state-machine.md"


class Status(StrEnum):
    AWAITING_CUSTOMER_CONFIRMATION = "awaiting_customer_confirmation"
    AWAITING_STAFF_APPROVAL = "awaiting_staff_approval"
    APPROVED = "approved"
    REFUNDED = "refunded"
    INELIGIBLE = "ineligible"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


OPEN = frozenset({Status.AWAITING_CUSTOMER_CONFIRMATION, Status.AWAITING_STAFF_APPROVAL, Status.APPROVED})
FINAL = frozenset(Status) - OPEN


class Actor(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"  # always inside the customer's session, never with more rights than the customer
    STAFF = "staff"
    SYSTEM = "system"  # the backend itself, on its own clock or inside another actor's transaction


class Control(StrEnum):
    """Who may change things in a conversation. There is no way back to the agent in v1."""

    AGENT = "agent"
    HUMAN_CONTROLLED = "human_controlled"


HANDOFF_ACTORS = (Actor.CUSTOMER, Actor.AGENT, Actor.STAFF)


@dataclass(frozen=True)
class Check:
    name: str
    protects: tuple[str, ...]  # product-contract invariants ("INV-4") and policy sections ("policy:window")
    verifies: str
    lab_disabled: bool = False  # not enforced by execute_refund in configuration C


CHECKS = (
    Check("actor_owns", ("INV-1",), "The session's customer owns the conversation, the order and the proposal."),
    Check("staff_role", ("INV-1",), "The session belongs to a staff member."),
    Check(
        "agent_in_control",
        ("INV-8",),
        "The conversation is not human_controlled, read inside the same transaction.",
    ),
    Check(
        "request_key_consistent",
        ("INV-6",),
        "A repeated request key with the same payload returns the stored result; "
        "with a different payload it is a conflict.",
    ),
    Check(
        "valid_values",
        ("INV-2",),
        "Quantities and amounts are positive integers, the lines belong to the order, "
        "and the currency is the policy currency.",
    ),
    Check(
        "no_confirmed_open_proposal",
        (),
        "The conversation has no open proposal that the customer already confirmed; an unconfirmed one is superseded.",
    ),
    Check(
        "policy_eligible",
        ("INV-5", "policy:eligible-orders", "policy:window", "policy:return", "policy:payment"),
        "Order status, time window, received-back units and a single payment record satisfy the policy; "
        "a staff approval cannot override it.",
    ),
    Check(
        "within_remaining",
        ("INV-4", "policy:remaining"),
        "Each line's quantity and amount fit what is left on it; at execution the line balance must still be "
        "exactly the one the proposal saw.",
    ),
    Check(
        "proposal_current",
        ("INV-3", "policy:validity"),
        "Not expired, the bound order and policy versions are still current, and the content hash matches.",
        lab_disabled=True,
    ),
    Check(
        "first_execution",
        ("INV-6",),
        "If the proposal already has a committed operation, its receipt is returned and nothing runs again.",
    ),
    Check("status_approved", ("INV-5",), "The proposal's status is approved.", lab_disabled=True),
    Check(
        "customer_confirmed",
        ("INV-5", "policy:approval"),
        "A stored confirmation by the proposal's customer for this content hash.",
        lab_disabled=True,
    ),
    Check(
        "staff_approved",
        ("INV-5", "policy:approval"),
        "A stored staff approval for this content hash.",
        lab_disabled=True,
    ),
    Check(
        "approval_used_once",
        ("INV-6",),
        "No committed operation uses this approval yet (also a unique constraint in the database).",
    ),
    Check(
        "within_window",
        ("policy:window",),
        "The proposal was created within the time window after delivery.",
        lab_disabled=True,
    ),
    Check("order_status_eligible", ("policy:eligible-orders",), "The order's status is eligible.", lab_disabled=True),
    Check("return_received", ("policy:return",), "Every refunded unit was received back.", lab_disabled=True),
)


@dataclass(frozen=True)
class Transition:
    event: str
    sources: frozenset[Status] | None  # None: this event creates the proposal
    target: Status
    actor: Actor
    checks: tuple[str, ...]
    when: str


_PROPOSE_CHECKS = ("actor_owns", "agent_in_control", "request_key_consistent", "valid_values")

TRANSITIONS = (
    Transition(
        "propose",
        None,
        Status.AWAITING_CUSTOMER_CONFIRMATION,
        Actor.AGENT,
        (*_PROPOSE_CHECKS, "no_confirmed_open_proposal", "policy_eligible", "within_remaining"),
        "The request passes the policy; the backend computes and stores the amount.",
    ),
    Transition(
        "propose",
        None,
        Status.INELIGIBLE,
        Actor.AGENT,
        (*_PROPOSE_CHECKS, "no_confirmed_open_proposal"),
        "The policy refuses; the reasons are stored as policy section IDs and cited to the customer.",
    ),
    Transition(
        "confirm",
        frozenset({Status.AWAITING_CUSTOMER_CONFIRMATION}),
        Status.AWAITING_STAFF_APPROVAL,
        Actor.CUSTOMER,
        ("actor_owns", "proposal_current"),
        "The customer presses confirm on the proposal card.",
    ),
    Transition(
        "approve",
        frozenset({Status.AWAITING_STAFF_APPROVAL}),
        Status.APPROVED,
        Actor.STAFF,
        ("staff_role", "proposal_current", "policy_eligible"),
        "A staff member approves in the console.",
    ),
    Transition(
        "execute",
        frozenset({Status.APPROVED}),
        Status.REFUNDED,
        Actor.AGENT,
        (
            "actor_owns",
            "agent_in_control",
            "request_key_consistent",
            "first_execution",
            "status_approved",
            "customer_confirmed",
            "staff_approved",
            "approval_used_once",
            "proposal_current",
            "within_window",
            "order_status_eligible",
            "return_received",
            "valid_values",
            "within_remaining",
        ),
        "The agent calls execute_refund(proposal_id); one transaction commits the refund and its receipt.",
    ),
    Transition(
        "reject",
        frozenset({Status.AWAITING_STAFF_APPROVAL}),
        Status.REJECTED,
        Actor.STAFF,
        ("staff_role",),
        "A staff member rejects in the console.",
    ),
    Transition(
        "cancel",
        OPEN,
        Status.CANCELLED,
        Actor.CUSTOMER,
        ("actor_owns",),
        "The customer declines or cancels before execution.",
    ),
    Transition(
        "expire",
        OPEN,
        Status.EXPIRED,
        Actor.SYSTEM,
        (),
        "The clock passed expires_at; applied by the next action that touches the proposal.",
    ),
    Transition(
        "order_or_policy_changed",
        OPEN,
        Status.INVALIDATED,
        Actor.SYSTEM,
        (),
        "The order's material version or the policy version differs from the bound one; applied by the next "
        "action that touches the proposal.",
    ),
    Transition(
        "superseded",
        frozenset({Status.AWAITING_CUSTOMER_CONFIRMATION}),
        Status.INVALIDATED,
        Actor.SYSTEM,
        (),
        "The agent creates a newer proposal in the same conversation (same transaction).",
    ),
    Transition(
        "handed_off",
        OPEN,
        Status.INVALIDATED,
        Actor.SYSTEM,
        (),
        "The conversation becomes human_controlled (same transaction).",
    ),
)


def _ordered(statuses: frozenset[Status]) -> list[Status]:
    return [status for status in Status if status in statuses]


def render_markdown() -> str:
    lines = [
        "# Proposal states and conversation control",
        "",
        "<!-- Generated from refund_agent/states.py by `uv run python -m refund_agent.states`. "
        "Do not edit by hand. -->",
        "",
        f"Open statuses: {', '.join(f'`{s}`' for s in _ordered(OPEN))}. "
        f"Final statuses: {', '.join(f'`{s}`' for s in _ordered(FINAL))}.",
        "",
        "## Proposal lifecycle (configuration A, the product)",
        "",
        "```mermaid",
        "stateDiagram-v2",
    ]
    arrows: dict[tuple[str, str], list[str]] = {}
    for t in TRANSITIONS:
        sources = ["[*]"] if t.sources is None else [s.value for s in _ordered(t.sources)]
        for source in sources:
            arrows.setdefault((source, t.target.value), []).append(t.event)
    for (source, target), events in arrows.items():
        lines.append(f"    {source} --> {target} : {' / '.join(events)}")
    lines += [
        "```",
        "",
        "## Transitions",
        "",
        "| Event | From | To | Actor | Checks | When |",
        "|---|---|---|---|---|---|",
    ]
    for t in TRANSITIONS:
        sources = "(new)" if t.sources is None else ", ".join(f"`{s}`" for s in _ordered(t.sources))
        checks = ", ".join(f"`{c}`" for c in t.checks) or "-"
        lines.append(f"| `{t.event}` | {sources} | `{t.target}` | {t.actor} | {checks} | {t.when} |")
    (execute,) = [t for t in TRANSITIONS if t.event == "execute"]
    lines += [
        "",
        "A retry of `execute` on a refunded proposal is not a transition: it returns the same receipt.",
        "",
        "## Checks",
        "",
        "The last two columns are about `execute_refund` only. Confirm and approve enforce their checks in every",
        "configuration.",
        "",
        "| Check | Protects | Verifies | execute in A | execute in C |",
        "|---|---|---|---|---|",
    ]
    for c in CHECKS:
        protects = ", ".join(c.protects) or "-"
        if c.name in execute.checks:
            in_a, in_c = "enforced", ("**not enforced**" if c.lab_disabled else "enforced")
        else:
            in_a = in_c = "-"
        lines.append(f"| `{c.name}` | {protects} | {c.verifies} | {in_a} | {in_c} |")
    lines += [
        "",
        "Configuration C exists only in the isolated evaluation harness, on a synthetic database. Because",
        "`status_approved` is not enforced there, `execute` can start from any status except `refunded`; the",
        "evaluator counts a refund without a valid confirmation and approval as an unauthorized committed action.",
        "",
        "## Conversation control",
        "",
        "```mermaid",
        "stateDiagram-v2",
        f"    [*] --> {Control.AGENT}",
        f"    {Control.AGENT} --> {Control.HUMAN_CONTROLLED} : hand_off by {', '.join(HANDOFF_ACTORS)}",
        "```",
        "",
        "Handing off invalidates the conversation's open proposals in the same transaction. From then on every",
        "agent write fails `agent_in_control`. There is no way back to the agent in v1.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    RENDERED_PATH.write_text(render_markdown(), encoding="utf-8", newline="\n")
    print(f"wrote {RENDERED_PATH.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
