"""Domain services of the refund flow: the backend decides (plan sections 5 and 6).

Each public function is one database transaction. Rows are locked in one order everywhere, the conversation and
then the proposal, so two transactions never wait for each other forever and a handoff and an agent write are
ordered. The actor comes from the caller's channel and session (the HTTP layer or the agent's tool executor), never
from a request body. Every business time comes from the `now` argument, never from the database clock.

execute() runs the checks of the execute transition of refund_agent/states.py, one function per check, in the
declared order; configuration C runs the lab transition, which leaves out the lab-disabled checks.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, NamedTuple

from sqlalchemy import Connection, Engine, RowMapping, text
from sqlalchemy.exc import IntegrityError

from refund_agent import eligibility, selection
from refund_agent.policy import Policy
from refund_agent.states import LAB_TRANSITIONS, OPEN, TRANSITIONS, Status

Configuration = Literal["A", "C"]
OPEN_STATUSES = [status.value for status in OPEN]
MAX_REASON = 500  # characters of a rejection reason, as the CHECK of staff_decisions allows


@dataclass(frozen=True)
class Actor:
    """Who acts, as the channel and the session establish it."""

    kind: Literal["customer", "agent", "staff"]
    user_id: str  # the signed-in customer (also for the agent, which acts in their session) or the staff member


class Refused(Exception):
    """A check refused the action. Nothing was committed, except closing an out-of-date proposal."""

    def __init__(self, check: str, detail: str = "") -> None:
        super().__init__(f"{check}: {detail}" if detail else check)
        self.check = check
        self.detail = detail


# Test-only failpoint (plan section 14): called with a point name and an ID inside a transaction, so tests can hold,
# break or crash it there. "execute" and "hand_off" come after the checks and before any write; "ledger" comes
# after a refund operation is written and before its ledger lines. None in normal operation; no request can set it.
failpoint: Callable[[str, str], None] | None = None


def _reach(point: str, key: str) -> None:
    if failpoint is not None:
        failpoint(point, key)


@dataclass(frozen=True)
class ProposalResult:
    id: str
    status: str
    amount_minor: int
    reasons: tuple[str, ...]  # policy section IDs, empty when eligible
    outcome: str  # eligible, refused or needs_person


def _digest(data: Any) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def proposal_content_hash(
    *,
    customer_id: str,
    order_id: str,
    units: list[tuple[str, int]],
    amount_minor: int,
    currency: str,
    payment_id: str | None,
    policy_version: str,
    policy_hash: str,
    order_material_version: int,
    expires_at: datetime,
) -> str:
    """The hash that binds a confirmation and an approval to the exact proposal (INV-3)."""
    return _digest(
        {
            "customer_id": customer_id,
            "order_id": order_id,
            "units": sorted([unit_id, amount] for unit_id, amount in units),
            "amount_minor": amount_minor,
            "currency": currency,
            "payment_id": payment_id,
            "policy_version": policy_version,
            "policy_hash": policy_hash,
            "order_material_version": order_material_version,
            "expires_at": expires_at.isoformat(),
        }
    )


# Small SQL helpers


def _one(conn: Connection, sql: str, **params: Any) -> RowMapping | None:
    return conn.execute(text(sql), params).mappings().first()


def _all(conn: Connection, sql: str, **params: Any) -> list[RowMapping]:
    return list(conn.execute(text(sql), params).mappings())


def _audit(
    conn: Connection,
    *,
    at: datetime,
    actor_type: str,
    actor_id: str | None,
    event: str,
    outcome: str,
    conversation_id: str | None = None,
    proposal_id: str | None = None,
    operation_id: str | None = None,
    reason: str | None = None,
    details: dict | None = None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO audit_events (at, actor_type, actor_id, conversation_id, proposal_id, operation_id, event, "
            "outcome, reason, details) VALUES (:at, :actor_type, :actor_id, :conversation_id, :proposal_id, "
            ":operation_id, :event, :outcome, :reason, CAST(:details AS jsonb))"
        ),
        {
            "at": at,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "conversation_id": conversation_id,
            "proposal_id": proposal_id,
            "operation_id": operation_id,
            "event": event,
            "outcome": outcome,
            "reason": reason,
            "details": json.dumps(details or {}),
        },
    )


def _record_rejection(engine: Engine, now: datetime, actor: Actor, event: str, refusal: Refused, **ids: Any) -> None:
    """A refused attempt is recorded in its own transaction, so the rollback of the attempt does not erase it."""
    with engine.begin() as conn:
        _audit(
            conn,
            at=now,
            actor_type=actor.kind,
            actor_id=actor.user_id,
            event=event,
            outcome="rejected",
            reason=refusal.check,
            details={"detail": refusal.detail},
            **ids,
        )


def _lock_conversation(conn: Connection, conversation_id: str) -> RowMapping | None:
    return _one(
        conn, "SELECT id, customer_id, control FROM conversations WHERE id = :id FOR UPDATE", id=conversation_id
    )


def _lock_proposal(conn: Connection, proposal_id: str) -> tuple[RowMapping | None, RowMapping | None]:
    """Lock the proposal's conversation, then the proposal: the one lock order of every transaction."""
    found = _one(conn, "SELECT conversation_id FROM proposals WHERE id = :id", id=proposal_id)
    if found is None:
        return None, None
    conversation = _lock_conversation(conn, found["conversation_id"])
    return conversation, _one(conn, "SELECT * FROM proposals WHERE id = :id FOR UPDATE", id=proposal_id)


def _set_status(conn: Connection, proposal_id: str, status: Status, reason: str | None) -> None:
    conn.execute(
        text("UPDATE proposals SET status = :status, status_reason = :reason WHERE id = :id"),
        {"status": status.value, "reason": reason, "id": proposal_id},
    )


def _out_of_date(conn: Connection, proposal: RowMapping, now: datetime, policy: Policy) -> tuple[Status, str] | None:
    """Whether an open proposal has expired or no longer matches the order or the policy (policy section validity)."""
    if not eligibility.proposal_active(proposal["expires_at"], now):
        return Status.EXPIRED, "expired"
    order = _one(conn, "SELECT material_version FROM orders WHERE id = :id", id=proposal["order_id"])
    bound = (proposal["order_material_version"], proposal["policy_version"], proposal["policy_hash"])
    if bound != (order["material_version"], policy.version, policy.content_hash()):
        return Status.INVALIDATED, "order_or_policy_changed"
    return None


def _close(conn: Connection, proposal: RowMapping, change: tuple[Status, str], now: datetime) -> None:
    status, reason = change
    _set_status(conn, proposal["id"], status, reason)
    _audit(
        conn,
        at=now,
        actor_type="system",
        actor_id=None,
        event="expire" if status is Status.EXPIRED else reason,
        outcome="committed",
        conversation_id=proposal["conversation_id"],
        proposal_id=proposal["id"],
    )


def _close_out_of_date(engine: Engine, proposal_id: str, now: datetime, policy: Policy) -> None:
    with engine.begin() as conn:
        _, proposal = _lock_proposal(conn, proposal_id)
        if proposal is not None and proposal["status"] in OPEN_STATUSES:
            change = _out_of_date(conn, proposal, now, policy)
            if change:
                _close(conn, proposal, change, now)


def _policy_order(conn: Connection, order_id: str, now: datetime) -> eligibility.Order:
    """The order as the policy functions see it, read inside the caller's transaction."""
    order = _one(conn, "SELECT status, purchased_at, delivered_at FROM orders WHERE id = :id", id=order_id)
    payments = _all(
        conn, "SELECT method, amount_minor FROM payments WHERE order_id = :id ORDER BY sequential", id=order_id
    )
    units = _all(
        conn,
        "SELECT u.id, u.paid_minor, u.received_back_at, "
        "EXISTS (SELECT 1 FROM ledger_lines l WHERE l.order_unit_id = u.id) AS refunded "
        "FROM order_units u WHERE u.order_id = :id ORDER BY u.unit_no",
        id=order_id,
    )
    return eligibility.Order(
        status=order["status"],
        purchased_at=order["purchased_at"],
        delivered_at=order["delivered_at"],
        payments=tuple(eligibility.Payment(p["method"], p["amount_minor"]) for p in payments),
        units=tuple(
            eligibility.Unit(
                u["id"],
                u["paid_minor"],
                received_back=u["received_back_at"] is not None and u["received_back_at"] <= now,
                refunded=u["refunded"],
            )
            for u in units
        ),
    )


# A proposal that lapsed before it was paid (policy sections window and validity): it expired, or stopped being valid
# because the order or the policy changed. One that expired while nobody touched it is still open in the table, so its
# time counts, not only its status. Takes :open (OPEN_STATUSES) and :now.
_LAPSED = (
    "(p.status = 'expired' OR (p.status = 'invalidated' AND p.status_reason = 'order_or_policy_changed') "
    "OR (p.status = ANY(:open) AND p.expires_at <= :now))"
)


def _earlier_on_time_units(
    conn: Connection, policy: Policy, delivered_at: datetime | None, units: list[str], now: datetime
) -> frozenset[str]:
    """The units that had an earlier proposal created in time that then expired, or stopped being valid because the
    order or the policy changed, before it was paid (policy sections window and validity). A proposal that expired
    while nobody touched it is still open in the table, so its time counts, not only its status. A proposal the
    customer replaced, cancelled or had rejected, or that a handoff closed, does not count."""
    if delivered_at is None:
        return frozenset()
    found = conn.execute(
        text(
            "SELECT DISTINCT pu.order_unit_id FROM proposals p JOIN proposal_units pu ON pu.proposal_id = p.id "
            f"WHERE pu.order_unit_id = ANY(:units) AND p.created_at <= :deadline AND {_LAPSED}"
        ),
        {
            "units": units,
            "deadline": eligibility.refund_deadline(policy, delivered_at),
            "open": OPEN_STATUSES,
            "now": now,
        },
    ).scalars()
    return frozenset(found)


def _look_alikes_unnamed(
    conn: Connection, conversation_id: str, customer_id: str, unit_ids: list[str]
) -> tuple[selection.Kind, ...]:
    """The look-alikes among the customer's orders that the conversation does not yet tell apart for these units
    (refund_agent/selection.py), read inside the proposal's transaction: every unit of the customer not yet refunded,
    as kinds of one product in one order, and what the customer and the agent wrote, in order. Order dates are UTC."""
    units = _all(
        conn,
        "SELECT u.id, u.order_id, u.product_name, o.purchased_at, o.delivered_at FROM order_units u "
        "JOIN orders o ON o.id = u.order_id WHERE o.customer_id = :customer "
        "AND NOT EXISTS (SELECT 1 FROM ledger_lines l WHERE l.order_unit_id = u.id) "
        "ORDER BY o.purchased_at, u.order_id, u.unit_no",
        customer=customer_id,
    )
    grouped: dict[tuple[str, str], list[RowMapping]] = {}
    for unit in units:
        grouped.setdefault((unit["order_id"], unit["product_name"]), []).append(unit)
    kinds = [
        selection.Kind(
            order_id,
            product,
            same[0]["purchased_at"].astimezone(UTC).date(),
            same[0]["delivered_at"].astimezone(UTC).date() if same[0]["delivered_at"] else None,
            tuple(unit["id"] for unit in same),
        )
        for (order_id, product), same in grouped.items()
    ]
    written = conn.execute(
        text(
            "SELECT author, content_untrusted FROM messages "
            "WHERE conversation_id = :id AND author IN ('customer', 'agent') ORDER BY seq"
        ),
        {"id": conversation_id},
    ).all()
    return selection.look_alikes_unnamed(kinds, unit_ids, [(author, said) for author, said in written])


def _result(proposal: RowMapping) -> ProposalResult:
    outcome = proposal["status_reason"] if proposal["status"] == Status.INELIGIBLE else "eligible"
    return ProposalResult(
        proposal["id"], proposal["status"], proposal["amount_minor"], tuple(proposal["reasons"]), outcome
    )


# Conversation


def open_conversation(engine: Engine, actor: Actor, now: datetime) -> str:
    """The customer opens a conversation; the agent then acts in it, in the customer's session."""
    conversation_id = _new_id("conv")
    with engine.begin() as conn:
        user = _one(conn, "SELECT role FROM users WHERE id = :id", id=actor.user_id)
        if actor.kind != "customer" or user is None or user["role"] != "customer":
            raise Refused("actor_owns")
        conn.execute(
            text(
                "INSERT INTO conversations (id, customer_id, control, created_at) "
                "VALUES (:id, :customer, 'agent', :now)"
            ),
            {"id": conversation_id, "customer": actor.user_id, "now": now},
        )
        _audit(
            conn,
            at=now,
            actor_type="customer",
            actor_id=actor.user_id,
            event="open_conversation",
            outcome="committed",
            conversation_id=conversation_id,
        )
    return conversation_id


# Propose


def propose(
    engine: Engine,
    actor: Actor,
    conversation_id: str,
    order_id: str,
    unit_ids: list[str],
    request_key: str,
    now: datetime,
    policy: Policy,
    summary_untrusted: str = "",
    *,
    referral: bool = False,
) -> ProposalResult:
    """Store a proposal for these units with the amount the backend computes, eligible or not.

    Checks in the order of the propose transition: actor_owns, agent_in_control, request_key_consistent,
    valid_values, units_named, then (for an eligible request) no_confirmed_open_proposal and policy_eligible. A
    repeated request key returns its proposal before units_named, whatever the conversation said since.

    With referral (refer_to_staff), the request is stored only when the policy sends it to a staff member; any other
    decision is refused before anything is written, and every refusal is recorded as the handoff's.
    """
    request_hash = _digest({"conversation": conversation_id, "order": order_id, "units": sorted(unit_ids)})
    try:
        with engine.begin() as conn:
            conversation = _lock_conversation(conn, conversation_id)
            order = _one(
                conn, "SELECT id, customer_id, material_version, delivered_at FROM orders WHERE id = :id", id=order_id
            )
            if (
                actor.kind != "agent"
                or conversation is None
                or order is None
                or conversation["customer_id"] != actor.user_id
                or order["customer_id"] != actor.user_id
            ):
                raise Refused("actor_owns")
            if conversation["control"] != "agent":
                raise Refused("agent_in_control")
            existing = _one(conn, "SELECT * FROM proposals WHERE request_key = :key", key=request_key)
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise Refused("request_key_consistent", "the same key was used for another request")
                return _result(existing)
            units = _all(
                conn,
                "SELECT id, paid_minor FROM order_units WHERE order_id = :order AND id = ANY(:ids)",
                order=order_id,
                ids=list(unit_ids),
            )
            if not unit_ids or len(set(unit_ids)) != len(unit_ids) or len(units) != len(unit_ids):
                raise Refused("valid_values", "the units must be distinct units of this order")
            look_alikes = _look_alikes_unnamed(conn, conversation_id, actor.user_id, list(unit_ids))
            if look_alikes:
                raise Refused("units_named", selection.refusal(look_alikes))

            # An out-of-date open proposal is closed first, so it never blocks a new one.
            open_proposal = _one(
                conn,
                "SELECT * FROM proposals WHERE conversation_id = :id AND status = ANY(:open) FOR UPDATE",
                id=conversation_id,
                open=OPEN_STATUSES,
            )
            if open_proposal is not None:
                change = _out_of_date(conn, open_proposal, now, policy)
                if change:
                    _close(conn, open_proposal, change, now)
                    open_proposal = None

            policy_order = _policy_order(conn, order_id, now)
            earlier = _earlier_on_time_units(conn, policy, order["delivered_at"], list(unit_ids), now)
            decision = eligibility.evaluate(policy, policy_order, tuple(unit_ids), now, earlier_on_time_units=earlier)
            eligible = decision.outcome is eligibility.Outcome.ELIGIBLE
            if referral and decision.outcome is not eligibility.Outcome.NEEDS_PERSON:
                raise Refused("handoff_reason", _not_for_staff(policy, decision))
            if eligible and open_proposal is not None:
                if open_proposal["status"] != Status.AWAITING_CUSTOMER_CONFIRMATION:
                    raise Refused("no_confirmed_open_proposal", "the customer already confirmed another proposal")
                _set_status(conn, open_proposal["id"], Status.INVALIDATED, "superseded")
                _audit(
                    conn,
                    at=now,
                    actor_type="system",
                    actor_id=None,
                    event="superseded",
                    outcome="committed",
                    conversation_id=conversation_id,
                    proposal_id=open_proposal["id"],
                )

            payments = _all(conn, "SELECT id FROM payments WHERE order_id = :id ORDER BY sequential", id=order_id)
            payment_id = payments[0]["id"] if eligibility.single_valid_payment(policy_order) else None
            amounts = [(unit["id"], unit["paid_minor"]) for unit in units]
            amount = sum(paid for _, paid in amounts)
            expires_at = eligibility.proposal_expires_at(policy, now)
            content_hash = proposal_content_hash(
                customer_id=actor.user_id,
                order_id=order_id,
                units=amounts,
                amount_minor=amount,
                currency=policy.currency,
                payment_id=payment_id,
                policy_version=policy.version,
                policy_hash=policy.content_hash(),
                order_material_version=order["material_version"],
                expires_at=expires_at,
            )
            status = Status.AWAITING_CUSTOMER_CONFIRMATION if eligible else Status.INELIGIBLE
            proposal_id = _new_id("prop")
            conn.execute(
                text(
                    "INSERT INTO proposals (id, request_key, request_hash, conversation_id, customer_id, order_id, "
                    "payment_id, amount_minor, currency, policy_version, policy_hash, order_material_version, status, "
                    "status_reason, reasons, created_at, expires_at, content_hash, summary_untrusted) VALUES (:id, "
                    ":request_key, :request_hash, :conversation_id, :customer_id, :order_id, :payment_id, :amount, "
                    ":currency, :policy_version, :policy_hash, :material_version, :status, :status_reason, :reasons, "
                    ":now, :expires_at, :content_hash, :summary)"
                ),
                {
                    "id": proposal_id,
                    "request_key": request_key,
                    "request_hash": request_hash,
                    "conversation_id": conversation_id,
                    "customer_id": actor.user_id,
                    "order_id": order_id,
                    "payment_id": payment_id,
                    "amount": amount,
                    "currency": policy.currency,
                    "policy_version": policy.version,
                    "policy_hash": policy.content_hash(),
                    "material_version": order["material_version"],
                    "status": status.value,
                    "status_reason": None if eligible else decision.outcome.value,
                    "reasons": list(decision.reasons),
                    "now": now,
                    "expires_at": expires_at,
                    "content_hash": content_hash,
                    "summary": summary_untrusted,
                },
            )
            for unit_id, paid in amounts:
                conn.execute(
                    text("INSERT INTO proposal_units (proposal_id, order_unit_id, amount_minor) VALUES (:p, :u, :a)"),
                    {"p": proposal_id, "u": unit_id, "a": paid},
                )
            _audit(
                conn,
                at=now,
                actor_type="agent",
                actor_id=actor.user_id,
                event="propose",
                outcome="committed",
                conversation_id=conversation_id,
                proposal_id=proposal_id,
                details={"status": status.value, "reasons": list(decision.reasons)},
            )
            return ProposalResult(proposal_id, status.value, amount, decision.reasons, decision.outcome.value)
    except Refused as refusal:
        event = "hand_off" if referral else "propose"
        _record_rejection(engine, now, actor, event, refusal, conversation_id=conversation_id)
        raise


# What any refusal of a handoff adds; a yes to an offer the check could not read is the exception.
_HANDOFF_TAIL = (
    " If a rule refuses the request, give its reason and what the policy allows, without offering a person. Hand off "
    "with customer_asked only when the customer clearly asks for a person."
)


def _not_for_staff(policy: Policy, decision: eligibility.Decision) -> str:
    """Why a handoff for a staff decision was refused: the policy decides these units itself, and what to do."""
    if decision.outcome is eligibility.Outcome.ELIGIBLE:
        return (
            "the policy allows a refund of these units now, so no staff member decides it. If the customer asked for "
            "them, call propose_refund with them and follow its result."
        )
    cited = ", ".join(f"({policy.citation(reason)})" for reason in decision.reasons)
    refused = f"the policy refuses a refund of these units {cited}."
    if "eligible-orders" in decision.reasons:  # refused only for an order not delivered: the policy's offer stands
        return (
            f"{refused} Tell the customer the order's status; cancelling it or changing its delivery is outside this "
            f"process, so offer a person for that ({policy.citation('eligible-orders')})."
        )
    return f"{refused} Tell the customer why, citing those sections.{_HANDOFF_TAIL}"


def _latest_proposal(conn: Connection, conversation_id: str) -> RowMapping | None:
    """The request in front of the agent: the conversation's latest proposal, whatever its status."""
    return _one(
        conn,
        "SELECT * FROM proposals WHERE conversation_id = :id ORDER BY created_at DESC, created_xact DESC LIMIT 1",
        id=conversation_id,
    )


def _refers(
    conn: Connection, proposal: RowMapping, order_id: str, unit_ids: Sequence[str], now: datetime, policy: Policy
) -> bool:
    """Whether a proposal records these very units as a case for a staff member, on the order and policy as now."""
    if (proposal["order_id"], proposal["status"], proposal["status_reason"]) != (
        order_id,
        "ineligible",
        "needs_person",
    ):
        return False
    units = conn.execute(
        text("SELECT order_unit_id FROM proposal_units WHERE proposal_id = :id"), {"id": proposal["id"]}
    ).scalars()
    return set(units) == set(unit_ids) and _out_of_date(conn, proposal, now, policy) is None


def refer_to_staff(
    engine: Engine,
    actor: Actor,
    conversation_id: str,
    order_id: str,
    unit_ids: Sequence[str],
    request_key: str,
    now: datetime,
    policy: Policy,
    summary_untrusted: str = "",
) -> ProposalResult:
    """Record a refund request that the policy sends to a staff member, for a handoff with shop_decided that names
    its order and units (final evaluation of v1.1, H77: the agent named them in a handoff before any proposal, the
    handoff was refused for want of one, and the agent then explained instead of proposing). The conversation's
    latest proposal is the record when it is that same request and still current; otherwise propose stores it with
    referral, which refuses, before writing anything, a request the policy decides itself."""
    if not order_id or not unit_ids:
        refusal = Refused("handoff_reason", "name the customer's order and the units of the request")
        _record_rejection(engine, now, actor, "hand_off", refusal, conversation_id=conversation_id)
        raise refusal
    with engine.connect() as conn:
        conversation = _one(conn, "SELECT customer_id FROM conversations WHERE id = :id", id=conversation_id)
        owned = actor.kind == "agent" and conversation is not None and conversation["customer_id"] == actor.user_id
        latest = _latest_proposal(conn, conversation_id)
        if owned and latest is not None and _refers(conn, latest, order_id, unit_ids, now, policy):
            return _result(latest)
    return propose(
        engine,
        actor,
        conversation_id,
        order_id,
        list(unit_ids),
        request_key,
        now,
        policy,
        summary_untrusted,
        referral=True,
    )


# Customer and staff decisions


def confirm(
    engine: Engine,
    actor: Actor,
    proposal_id: str,
    decision: Literal["confirmed", "declined"],
    now: datetime,
    policy: Policy,
) -> str:
    """The customer's button on the proposal card. Only a proposal ID and a decision come in (INV-2).

    A decline is told to the agent by a notice stored with it, as a cancellation is (agent/notices.py), also when the
    proposal had already expired or stopped being valid; a confirmation is told with the staff decision that follows.
    """
    pending: Refused | None = None
    try:
        with engine.begin() as conn:
            _, proposal = _lock_proposal(conn, proposal_id)
            if actor.kind != "customer" or proposal is None or proposal["customer_id"] != actor.user_id:
                raise Refused("actor_owns")
            if proposal["status"] != Status.AWAITING_CUSTOMER_CONFIRMATION:
                raise Refused("invalid_transition", f"the proposal is {proposal['status']}")
            if decision == "declined":
                # Final evaluation of v1.1, 2026-10-26: told nothing of a decline, the agent said seven times that the
                # declined request still waited for the customer's button.
                _store_notice(conn, f"notice-decline-{proposal_id}", proposal, "declined", now)
            change = _out_of_date(conn, proposal, now, policy)
            if change:
                _close(conn, proposal, change, now)
                pending = Refused("proposal_current", change[1])
                _audit(
                    conn,
                    at=now,
                    actor_type="customer",
                    actor_id=actor.user_id,
                    event="confirm",
                    outcome="rejected",
                    proposal_id=proposal_id,
                    reason=pending.check,
                )
                new_status = change[0].value
            else:
                conn.execute(
                    text(
                        "INSERT INTO customer_confirmations (id, proposal_id, customer_id, decision, content_hash, "
                        "decided_at) VALUES (:id, :proposal, :customer, :decision, :hash, :now)"
                    ),
                    {
                        "id": _new_id("conf"),
                        "proposal": proposal_id,
                        "customer": actor.user_id,
                        "decision": decision,
                        "hash": proposal["content_hash"],
                        "now": now,
                    },
                )
                status = Status.AWAITING_STAFF_APPROVAL if decision == "confirmed" else Status.CANCELLED
                _set_status(conn, proposal_id, status, None if decision == "confirmed" else "declined")
                _audit(
                    conn,
                    at=now,
                    actor_type="customer",
                    actor_id=actor.user_id,
                    event="confirm",
                    outcome="committed",
                    conversation_id=proposal["conversation_id"],
                    proposal_id=proposal_id,
                    details={"decision": decision},
                )
                new_status = status.value
    except Refused as refusal:
        _record_rejection(engine, now, actor, "confirm", refusal, proposal_id=proposal_id)
        raise
    if pending:
        raise pending
    return new_status


def decide(
    engine: Engine,
    actor: Actor,
    proposal_id: str,
    decision: Literal["approved", "rejected"],
    now: datetime,
    policy: Policy,
    reason: str | None = None,
) -> str:
    """The staff member's approval or rejection. An approval never overrides the policy (INV-5). A rejection carries
    the reason the staff member gives the customer, an approval none (migrations/sql/0006_rejection_reason.sql)."""
    pending: Refused | None = None
    reason = (reason or "").strip() or None
    try:
        with engine.begin() as conn:
            _, proposal = _lock_proposal(conn, proposal_id)
            user = _one(conn, "SELECT role FROM users WHERE id = :id", id=actor.user_id)
            if actor.kind != "staff" or user is None or user["role"] != "staff":
                raise Refused("staff_role")
            if proposal is None or proposal["status"] != Status.AWAITING_STAFF_APPROVAL:
                raise Refused("invalid_transition", "the proposal is not awaiting a staff decision")
            if decision == "rejected" and (reason is None or len(reason) > MAX_REASON):
                raise Refused(
                    "valid_values", f"a rejection needs a reason for the customer, 1 to {MAX_REASON} characters"
                )
            if decision == "approved" and reason is not None:
                raise Refused("valid_values", "an approval takes no reason")
            change = _out_of_date(conn, proposal, now, policy)
            if change:
                _close(conn, proposal, change, now)
                pending = Refused("proposal_current", change[1])
                _audit(
                    conn,
                    at=now,
                    actor_type="staff",
                    actor_id=actor.user_id,
                    event="decide",
                    outcome="rejected",
                    proposal_id=proposal_id,
                    reason=pending.check,
                )
                new_status = change[0].value
            else:
                if decision == "approved":
                    units = [
                        row["order_unit_id"]
                        for row in _all(
                            conn, "SELECT order_unit_id FROM proposal_units WHERE proposal_id = :id", id=proposal_id
                        )
                    ]
                    # The time limit counts at the request, the proposal's creation; the units' state counts now.
                    verdict = eligibility.evaluate(
                        policy, _policy_order(conn, proposal["order_id"], now), tuple(units), proposal["created_at"]
                    )
                    if verdict.outcome is not eligibility.Outcome.ELIGIBLE:
                        raise Refused("policy_eligible", ", ".join(verdict.reasons))
                decision_id = _new_id("dec")
                conn.execute(
                    text(
                        "INSERT INTO staff_decisions "
                        "(id, proposal_id, staff_id, decision, content_hash, decided_at, reason) "
                        "VALUES (:id, :proposal, :staff, :decision, :hash, :now, :reason)"
                    ),
                    {
                        "id": decision_id,
                        "proposal": proposal_id,
                        "staff": actor.user_id,
                        "decision": decision,
                        "hash": proposal["content_hash"],
                        "now": now,
                        "reason": reason,
                    },
                )
                # The agent must be told, even if the server stops right after this commit: the notice commits with
                # the decision, and its ID, one per decision, lets a second delivery be recognised.
                conn.execute(
                    text(
                        "INSERT INTO agent_notices (id, conversation_id, proposal_id, decision, created_at) "
                        "VALUES (:id, :conversation, :proposal, :decision, :now)"
                    ),
                    {
                        "id": f"notice-{decision_id}",
                        "conversation": proposal["conversation_id"],
                        "proposal": proposal_id,
                        "decision": decision,
                        "now": now,
                    },
                )
                status = Status.APPROVED if decision == "approved" else Status.REJECTED
                _set_status(conn, proposal_id, status, None)
                _audit(
                    conn,
                    at=now,
                    actor_type="staff",
                    actor_id=actor.user_id,
                    event="decide",
                    outcome="committed",
                    conversation_id=proposal["conversation_id"],
                    proposal_id=proposal_id,
                    details={"decision": decision},
                )
                new_status = status.value
    except Refused as refusal:
        _record_rejection(engine, now, actor, "decide", refusal, proposal_id=proposal_id)
        raise
    if pending:
        raise pending
    return new_status


def _store_notice(
    conn: Connection, notice_id: str, proposal: RowMapping, decision: Literal["cancelled", "declined"], now: datetime
) -> None:
    """A notice to the agent of the customer's button, written in the button's transaction."""
    conn.execute(
        text(
            "INSERT INTO agent_notices (id, conversation_id, proposal_id, decision, created_at) "
            "VALUES (:id, :conversation, :proposal, :decision, :now)"
        ),
        {
            "id": notice_id,
            "conversation": proposal["conversation_id"],
            "proposal": proposal["id"],
            "decision": decision,
            "now": now,
        },
    )


def cancel(engine: Engine, actor: Actor, proposal_id: str, now: datetime, policy: Policy) -> str:
    """The customer cancels an open proposal, before or after confirming, as long as it is not refunded.

    A proposal that has already expired or become invalid is closed with that status instead: either way no money
    moves, which is what the customer asked for. Either way the agent is told, by a notice stored with the change, as
    for a staff decision (agent/notices.py).
    """
    try:
        with engine.begin() as conn:
            _, proposal = _lock_proposal(conn, proposal_id)
            if actor.kind != "customer" or proposal is None or proposal["customer_id"] != actor.user_id:
                raise Refused("actor_owns")
            if proposal["status"] not in OPEN_STATUSES:
                raise Refused("invalid_transition", f"the proposal is {proposal['status']}")
            # The agent is told of the button, as of a staff decision: the notice commits with the cancellation
            # (review of the model comparison, 2026-10-24: in D28 the agent, told nothing, asked for the cancel).
            _store_notice(conn, f"notice-cancel-{proposal_id}", proposal, "cancelled", now)
            change = _out_of_date(conn, proposal, now, policy)
            if change:
                _close(conn, proposal, change, now)
                return change[0].value
            _set_status(conn, proposal_id, Status.CANCELLED, "cancelled_by_customer")
            _audit(
                conn,
                at=now,
                actor_type="customer",
                actor_id=actor.user_id,
                event="cancel",
                outcome="committed",
                conversation_id=proposal["conversation_id"],
                proposal_id=proposal_id,
            )
            return Status.CANCELLED.value
    except Refused as refusal:
        _record_rejection(engine, now, actor, "cancel", refusal, proposal_id=proposal_id)
        raise


# Handoff


def hand_off(
    engine: Engine,
    actor: Actor,
    conversation_id: str,
    reason: str,
    now: datetime,
    *,
    origin: Literal["customer", "agent"] | None = None,
    customer_goal_untrusted: str = "",
    confirmed_facts_untrusted: str = "",
    decision_needed_untrusted: str = "",
) -> str:
    """A person takes over: the conversation becomes human_controlled and its open proposal is invalidated.

    The customer's button records origin "customer"; a staff member's takeover records "staff" and the case as
    taken by them. The agent's tool records "agent", or "customer" when the customer asked in the chat; that is the
    agent's claim, and the audit keeps the agent as the actor. A second request returns the existing handoff.
    """
    if not reason:
        raise ValueError("a handoff needs a reason")
    try:
        with engine.begin() as conn:
            conversation = _lock_conversation(conn, conversation_id)
            if conversation is None:
                raise Refused("actor_owns")
            if actor.kind == "staff":
                user = _one(conn, "SELECT role FROM users WHERE id = :id", id=actor.user_id)
                if user is None or user["role"] != "staff":
                    raise Refused("staff_role")
                recorded_origin = "staff"
            elif conversation["customer_id"] != actor.user_id:
                raise Refused("actor_owns")
            elif actor.kind == "customer":
                recorded_origin = "customer"
            else:
                recorded_origin = origin or "agent"
                if recorded_origin not in ("agent", "customer"):
                    raise Refused("valid_values", "the agent reports origin 'agent' or 'customer'")

            if conversation["control"] == "human_controlled":
                existing = _one(
                    conn,
                    "SELECT id FROM handoffs WHERE conversation_id = :id ORDER BY created_at DESC LIMIT 1",
                    id=conversation_id,
                )
                return existing["id"]

            _reach("hand_off", conversation_id)
            # Prior actions come from the audit log, so the staff member can trust them. They are read before this
            # transaction adds its own events.
            prior = [
                {
                    "at": row["at"].isoformat(),
                    "event": row["event"],
                    "proposal_id": row["proposal_id"],
                    "operation_id": row["operation_id"],
                }
                for row in _all(
                    conn,
                    "SELECT at, event, proposal_id, operation_id FROM audit_events WHERE "
                    "conversation_id = :id AND outcome = 'committed' ORDER BY id",
                    id=conversation_id,
                )
            ]
            conn.execute(
                text("UPDATE conversations SET control = 'human_controlled' WHERE id = :id"), {"id": conversation_id}
            )
            open_proposal = _one(
                conn,
                "SELECT * FROM proposals WHERE conversation_id = :id AND status = ANY(:open) FOR UPDATE",
                id=conversation_id,
                open=OPEN_STATUSES,
            )
            if open_proposal is not None:
                _set_status(conn, open_proposal["id"], Status.INVALIDATED, "handed_off")
                _audit(
                    conn,
                    at=now,
                    actor_type="system",
                    actor_id=None,
                    event="handed_off",
                    outcome="committed",
                    conversation_id=conversation_id,
                    proposal_id=open_proposal["id"],
                )
            handoff_id = _new_id("hand")
            taken = actor.kind == "staff"
            conn.execute(
                text(
                    "INSERT INTO handoffs (id, conversation_id, origin, reason, created_at, pending_proposal_id, "
                    "prior_actions, customer_goal_untrusted, confirmed_facts_untrusted, decision_needed_untrusted, "
                    "status, taken_by, taken_at) VALUES (:id, :conversation, :origin, :reason, :now, :pending, "
                    "CAST(:prior AS jsonb), :goal, :facts, :decision, :status, :taken_by, :taken_at)"
                ),
                {
                    "id": handoff_id,
                    "conversation": conversation_id,
                    "origin": recorded_origin,
                    "reason": reason,
                    "now": now,
                    "pending": open_proposal["id"] if open_proposal is not None else None,
                    "prior": json.dumps(prior),
                    "goal": customer_goal_untrusted,
                    "facts": confirmed_facts_untrusted,
                    "decision": decision_needed_untrusted,
                    "status": "taken" if taken else "open",
                    "taken_by": actor.user_id if taken else None,
                    "taken_at": now if taken else None,
                },
            )
            _audit(
                conn,
                at=now,
                actor_type=actor.kind,
                actor_id=actor.user_id,
                event="hand_off",
                outcome="committed",
                conversation_id=conversation_id,
                details={"handoff_id": handoff_id, "origin": recorded_origin, "reason": reason},
            )
            return handoff_id
    except Refused as refusal:
        _record_rejection(engine, now, actor, "hand_off", refusal, conversation_id=conversation_id)
        raise


# The cases in which the agent may hand a conversation to a person (policy v2, section exceptions).
HANDOFF_REASONS = ("customer_asked", "shop_decided", "return_disputed", "delivery_disputed", "shipping_refund")
_NEEDS_ORDER = ("return_disputed", "delivery_disputed")


@dataclass(frozen=True)
class Assessment:
    """What propose would decide for these units at that moment, and the facts each reason rests on."""

    outcome: str  # eligible, refused or needs_person
    reasons: tuple[str, ...]  # policy section IDs, in the order eligibility.evaluate() gives them
    amount_minor: int | None  # only when eligible: nothing to promise otherwise
    order: dict[str, Any]
    units: tuple[dict[str, Any], ...]


def assess(
    engine: Engine,
    actor: Actor,
    conversation_id: str,
    order_id: str,
    unit_ids: Sequence[str],
    now: datetime,
    policy: Policy,
) -> Assessment:
    """The decision propose would make for these units now, with the facts behind it, and nothing written (plan
    change log, 2026-10-21, v1.1 step 2). It reads with the queries and the policy functions of propose, so the two
    agree on the same data. An assessment reserves nothing and can go stale: propose and execute decide again.
    A refused read is not recorded, as no other read is."""
    with engine.connect() as conn:
        conversation = _one(conn, "SELECT customer_id FROM conversations WHERE id = :id", id=conversation_id)
        order = _one(conn, "SELECT id, customer_id, delivered_at FROM orders WHERE id = :id", id=order_id)
        if (
            actor.kind != "agent"
            or conversation is None
            or order is None
            or conversation["customer_id"] != actor.user_id
            or order["customer_id"] != actor.user_id
        ):
            raise Refused("actor_owns")
        names = dict(
            conn.execute(
                text("SELECT id, product_name FROM order_units WHERE order_id = :order AND id = ANY(:ids)"),
                {"order": order_id, "ids": list(unit_ids)},
            ).all()
        )
        if not unit_ids or len(set(unit_ids)) != len(unit_ids) or len(names) != len(unit_ids):
            raise Refused("valid_values", "the units must be distinct units of this order")
        policy_order = _policy_order(conn, order_id, now)
        earlier = _earlier_on_time_units(conn, policy, order["delivered_at"], list(unit_ids), now)
        receipts = dict(
            conn.execute(
                text(
                    "SELECT l.order_unit_id, o.receipt_number FROM ledger_lines l "
                    "JOIN refund_operations o ON o.id = l.operation_id WHERE l.order_unit_id = ANY(:ids)"
                ),
                {"ids": list(unit_ids)},
            ).all()
        )
    decision = eligibility.evaluate(policy, policy_order, tuple(unit_ids), now, earlier_on_time_units=earlier)
    eligible = decision.outcome is eligibility.Outcome.ELIGIBLE
    delivered = policy_order.delivered_at
    by_id = {unit.id: unit for unit in policy_order.units}
    return Assessment(
        outcome=decision.outcome.value,
        reasons=decision.reasons,
        amount_minor=decision.amount_minor if eligible else None,
        order={
            "order_id": order_id,
            "status": policy_order.status,
            "delivered_at": delivered,
            "refund_deadline": eligibility.refund_deadline(policy, delivered) if delivered else None,
            "payment_records": len(policy_order.payments),
            "one_valid_payment": eligibility.single_valid_payment(policy_order),
        },
        units=tuple(
            {
                "unit_id": unit_id,
                "product": names[unit_id],
                "paid_minor": by_id[unit_id].paid_minor,
                "received_back": by_id[unit_id].received_back,
                "refunded": by_id[unit_id].refunded,
                "receipt_number": receipts.get(unit_id),
                "earlier_on_time_proposal": unit_id in earlier,
            }
            for unit_id in unit_ids
        ),
    )


def proposal_context(engine: Engine, proposal_id: str, policy: Policy) -> list[tuple[str, str]]:
    """The policy sections the circumstances of an eligible proposal rest on, beyond its amount, each with its fact
    from the records, for the agent to tell the customer (final evaluation of v1.1, 2026-10-26: the result gave only the
    amount section, and the scenarios required window 9 times, validity 10 and approval 6 where the agent left them
    out; a refusal's result gives its sections, and all 98 required refusal citations were shown). In the order:

    - window: the refund deadline falls before this proposal expires, so the limit passes while it is open;
    - validity: an earlier proposal for any of these units lapsed before it was paid (_LAPSED), so a new one was needed;
    - approval: an earlier proposal for any of these units was cancelled or declined by the customer, or rejected by a
      staff member, so this one needs both decisions again.

    "Earlier" is any proposal of the customer made before this one, in any conversation; a proposal the customer
    replaced with a change, or that a handoff closed, counts for neither."""
    with engine.connect() as conn:
        proposal = _one(
            conn,
            "SELECT p.*, o.delivered_at FROM proposals p JOIN orders o ON o.id = p.order_id WHERE p.id = :id",
            id=proposal_id,
        )
        # Each earlier proposal with the names of the units it shares with this one, and only those: one for the bowl
        # alone is not a request "for these items" when this one adds the plate (review of 2026-10-27).
        earlier = (
            conn.execute(
                text(
                    f"SELECT p.id, p.status, p.created_at, {_LAPSED} AS lapsed, "
                    "array_agg(u.product_name ORDER BY u.id) AS products "
                    "FROM proposals p JOIN proposal_units pu ON pu.proposal_id = p.id "
                    "JOIN order_units u ON u.id = pu.order_unit_id "
                    "WHERE p.customer_id = :customer AND (p.created_at, p.created_xact) < "
                    "(SELECT created_at, created_xact FROM proposals WHERE id = :id) "
                    "AND pu.order_unit_id IN (SELECT order_unit_id FROM proposal_units WHERE proposal_id = :id) "
                    "GROUP BY p.id ORDER BY p.created_at, p.created_xact"
                ),
                {
                    "customer": proposal["customer_id"],
                    "id": proposal_id,
                    "open": OPEN_STATUSES,
                    "now": proposal["created_at"],
                },
            )
            .mappings()
            .all()
        )
    context = []
    delivered = proposal["delivered_at"]
    deadline = eligibility.refund_deadline(policy, delivered) if delivered else None
    if deadline is not None and deadline < proposal["expires_at"]:
        context.append(
            (
                "window",
                f"the {policy.rules.refund_window_days}-day limit after delivery ends at {deadline:%Y-%m-%d %H:%M} "
                "UTC, and a request counts as made when its proposal is created, so this one is on time",
            )
        )

    def request(p: RowMapping) -> str:
        return f"an earlier request for the {' and the '.join(p['products'])}"

    def lapse(p: RowMapping) -> str:
        return (
            "stopped being valid because the order or the policy changed"
            if p["status"] == Status.INVALIDATED
            else ("expired")
        )

    lapsed = [f"{request(p)} lapsed before it was paid ({p['id']} {lapse(p)})" for p in earlier if p["lapsed"]]
    if lapsed:
        context.append(("validity", f"{'; '.join(lapsed)}, so a new proposal was needed"))
    closed = [
        f"{request(p)} ended unpaid ({p['id']} was "
        f"{'rejected by a staff member' if p['status'] == Status.REJECTED else 'cancelled'})"
        for p in earlier
        if p["status"] in (Status.CANCELLED, Status.REJECTED)
    ]
    if closed:
        context.append(
            (
                "approval",
                f"{'; '.join(closed)}, so this new proposal needs the customer's confirmation and a staff member's "
                "approval again",
            )
        )
    return context


_plain = selection.plain  # one way of comparing words, shared with the selection check


def _quoted(words: str, messages: Sequence[str]) -> bool:
    """Whether one of the messages contains these words, compared without case, curly quotes or spacing. An
    ellipsis stands for words left out, and the quote's own quotation marks and end punctuation do not count; each
    remaining part must have two letters at least, so a single letter quotes nothing."""
    parts = [part.strip(" \"'.,;:!?") for part in re.split("\\.\\.\\.|…", _plain(words))]
    parts = [part for part in parts if part]
    if not parts or any(sum(ch.isalpha() for ch in part) < 2 for part in parts):
        return False
    return any(all(part in _plain(message) for part in parts) for message in messages)


# What a request for a person looks like in words (plan change log, 2026-10-22 and 2026-10-23). In the contrasting
# baseline the agent quoted "Can I cancel it?", the customer's words, which ask for no one (D38). Code cannot read
# consent: this check refuses words that plainly ask for no one, and lets the reading of the rest stay the agent's.
# Negation and withdrawal count only where they apply (review of 2026-10-23): "Yes, please. My order has not arrived."
# accepts, and "Never mind the refund, I want to talk to a person." asks. Who a named person is, and what a question
# offers, need a reading of meaning that this check does not make (tests/test_request_for_person.py, known limits).
# The request no reading can doubt is the customer's own button (POST /api/conversations/{id}/handoff).
_PERSON = re.compile(
    r"\b(persons?|people|humans?|someone|somebody|anyone|anybody|staff|team|agents?|representatives?|reps?|"
    r"managers?|supervisors?|employees?|colleagues?|operators?)\b"
)
_NEGATION = re.compile(r"\b(no|not|never|nobody|nope|without|cannot)\b|n't\b")
_WITHDRAWN = re.compile(r"\b(never ?mind|forget it)\b")
_OFFER = re.compile(
    r"\b(connect|transfer|put you in touch|hand (?:you|this|it|the conversation) over|pass (?:you|this|it)|"
    r"talk (?:to|with)|speak (?:to|with)|chat with|offer|help (?:you|with))\b"
)
# A question about what the customer wants, or a condition on it: "Would you like me to ask a staff member to help?"
# (D37 try 3) offers a person without naming a way of contact.
_WISH = re.compile(
    r"\b(would you like|would you prefer|do you want|shall i|should i|want me to|"
    r"if you(?:'d| would)? like|if you want|if you wish|if you prefer)\b"
)
# The speaker's own role, as in "As a manager, I authorize a refund" (D23): a person word that names no one to talk to.
_OWN_ROLE = re.compile(r"\b(?:as|i'?m|i am) (?:a|an|the)(?: \w+)? $")
_ACCEPT = re.compile(r"(yes|yeah|yep|yup|sure|please do|please connect|go ahead|that would|i'?d like that)\b")
YES_WITHOUT_OFFER = (
    "that message is a yes, but your message just before it offers no person in words this check can read"
)


def _names_person(clause: str) -> bool:
    """A person word in the clause that is not the speaker's own role."""
    return any(not _OWN_ROLE.search(clause[: found.start()]) for found in _PERSON.finditer(clause))


def _asks_for_person(text_: str) -> bool:
    """A clause names a person with no negation anywhere in that clause, and nothing from it on withdraws the request:
    "I want to speak to a person, please, not an assistant" asks; "A human is not needed" and "Can I talk to a person?
    Actually, never mind." do not."""
    clauses = re.split(r"[.,;:!?]|\bbut\b", _plain(text_))
    asking = [i for i, clause in enumerate(clauses) if _names_person(clause) and not _NEGATION.search(clause)]
    return bool(asking) and not any(_WITHDRAWN.search(clause) for clause in clauses[asking[-1] :])


def _offers_person(text_: str) -> bool:
    """A part of one of the agent's sentences, cut again at a semicolon or "but", names a person, offers contact with
    one or asks whether the customer wants it, and holds no negation: "I cannot connect you with a staff member"
    offers no one, while in "I can't cancel it here, but I can connect you with a staff member" the offer stands."""
    return any(
        _PERSON.search(part) and (_OFFER.search(part) or _WISH.search(part)) and not _NEGATION.search(part)
        for part in re.split(r"[.!?;]|\bbut\b", _plain(text_))
    )


def _accepts(text_: str) -> bool:
    """The message's first sentence is a yes with no negation, and nothing after it withdraws it: "No, thanks" and
    "Yes, but not now" accept nothing, and "Yes, please. My order has not arrived." accepts."""
    plain = _plain(text_).lstrip(" \"'")
    first = re.split(r"[.!?]", plain)[0]
    return bool(_ACCEPT.match(first)) and not _NEGATION.search(first) and not _WITHDRAWN.search(plain)


def _latest_customer_words(messages: Sequence[tuple[str, str, str]], words: str, asking: str) -> tuple[int | None, str]:
    """The place of the customer's latest message when the quoted words are in it, or None and why not. An earlier
    request may have been withdrawn, so only the message in front of the agent counts. asking: what the words must
    ask, for the reason given when there are none."""
    if not words.strip():
        return None, f"customer_words must give the customer's own words that {asking}"
    customer = [i for i, (_, author, _) in enumerate(messages) if author == "customer"]
    if not any(_quoted(words, [messages[i][2]]) for i in customer):
        return None, "customer_words are not words the customer wrote in this conversation"
    if not _quoted(words, [messages[customer[-1]][2]]):
        return None, "those words are not in the customer's latest message, which is the request in front of you"
    return customer[-1], ""


# The shipping charge, in the words customers use for it.
_SHIPPING = re.compile(r"\b(shipping|postage|freight|delivery (?:charge|fee|cost))\b")
SHIPPING_OFFER = "Would you like a staff member to review the shipping charge?"  # the offer the refusal suggests


def _offers_person_for_shipping(text_: str) -> bool:
    """A part of the agent's message offers a person, as _offers_person reads it, and names the shipping charge in the
    same part: "Would you like a staff member to review the shipping charge?" offers one; "Shipping is never refunded
    automatically. Would you like a staff member to help with cancelling?" offers a person for something else."""
    return any(_offers_person(part) and _SHIPPING.search(part) for part in re.split(r"[.!?;]|\bbut\b", _plain(text_)))


def request_for_shipping_refund(messages: Sequence[tuple[str, str, str]], words: str) -> tuple[str | None, str]:
    """The customer message a request to refund shipping rests on, or None and why not.

    The customer's latest message must accept, with a yes (_accepts), the agent's offer of a staff member for the
    shipping charge in the message just before it (review of the model comparison, 2026-10-24). Until 2026-10-24 any
    words of that message naming the charge were enough, so a question ("Will the shipping I paid be refunded too, or
    just the kettle?", D39), a negation, a hypothetical or a past event handed the conversation off. Code does not tell
    a question from a request here: a question is answered from the policy, and a request is answered with the offer,
    whose yes is the request. A customer who asks for a person outright is handed off with customer_asked."""
    latest, unmet = _latest_customer_words(
        messages, words, "accept, with a yes, your offer of a staff member for the shipping charge"
    )
    if latest is None:
        return None, unmet
    said = messages[latest][2]
    if not _accepts(said):
        return None, "that message is not a yes to your offer of a staff member for the shipping charge"
    before = messages[latest - 1] if latest > 0 else None
    if before is None or before[1] != "agent" or not _offers_person_for_shipping(before[2]):
        return None, (
            "that message is a yes, but your message just before it offers no staff member for the shipping charge in "
            "words this check can read"
        )
    return messages[latest][0], ""


class PersonRequest(NamedTuple):
    message_id: str | None  # the customer message the request rests on, or None
    basis: str  # "names_person" or "accepts_offer" when there is a request; empty otherwise
    unmet: str  # why there is no request; empty when there is one


def request_for_person(messages: Sequence[tuple[str, str, str]], words: str) -> PersonRequest:
    """The customer message a request for a person rests on and what it rests on, or why there is none.

    messages: the conversation's (id, author, text), customer and agent only, in order. The quoted words must be in
    the customer's latest message, the one in front of the agent, since an earlier request may have been withdrawn.
    That message asks for a person when a clause of it names one (_asks_for_person), or when it accepts, with a yes,
    the offer of a person the agent made in the message just before it (_offers_person, _accepts). A yes with no
    offer in view gets its own reason, so the agent asks the offer plainly instead of asking the customer to word the
    request again (D37 try 3)."""
    latest, unmet = _latest_customer_words(messages, words, "ask for a person")
    if latest is None:
        return PersonRequest(None, "", unmet)
    message_id, _, said = messages[latest]
    if _asks_for_person(said):
        return PersonRequest(message_id, "names_person", "")
    if _accepts(said):
        before = messages[latest - 1] if latest > 0 else None
        if before is not None and before[1] == "agent" and _offers_person(before[2]):
            return PersonRequest(message_id, "accepts_offer", "")
        return PersonRequest(None, "", YES_WITHOUT_OFFER)
    return PersonRequest(
        None, "", "that message does not ask for a person: it names none, or declines one, or answers no offer of one"
    )


def _written(conn: Connection, conversation_id: str) -> list[tuple[str, str, str]]:
    """What the customer and the agent wrote in this conversation, as (id, author, text), in order."""
    rows = conn.execute(
        text(
            "SELECT id, author, content_untrusted FROM messages "
            "WHERE conversation_id = :id AND author IN ('customer', 'agent') ORDER BY seq"
        ),
        {"id": conversation_id},
    ).all()
    return [tuple(row) for row in rows]


def check_handoff_reason(
    engine: Engine,
    actor: Actor,
    conversation_id: str,
    reason: str,
    now: datetime,
    policy: Policy,
    order_id: str | None = None,
    unit_ids: Sequence[str] = (),
    customer_words: str = "",
) -> dict[str, Any]:
    """Before the agent hands off, the backend checks the reason it names against its own data (plan change log,
    2026-10-20 and 2026-10-21, v1.1 steps 3 and 2). Each check is about the request in front of the agent: the
    latest decision of this conversation, on the order and policy as they are now, is that a staff member takes the
    case; the named units of the named order are neither received back nor refunded; the named order is recorded as
    delivered; the words the agent quotes for a customer's request for a person are in the customer's latest message,
    and that message asks for one (request_for_person). Code cannot read consent, so a request that passes may still
    be misread: that reading stays the agent's, and the words are kept with the handoff for whoever reads it. A request
    worded otherwise still has a path: the agent offers a person, and the customer's yes is the request. A request to
    refund shipping rests on the customer's yes to the agent's offer of a staff member for the shipping charge, in
    the message just before (request_for_shipping_refund). A refusal says what
    to do instead and is recorded like any other; the customer's button and a staff member's takeover never come
    here. Returns what the check found, for the record: for customer_asked and shipping_refund, the ID of the customer
    message the request rests on; for shop_decided, the policy sections of the decision."""
    try:
        with engine.connect() as conn:
            conversation = _one(conn, "SELECT customer_id FROM conversations WHERE id = :id", id=conversation_id)
            if actor.kind != "agent" or conversation is None or conversation["customer_id"] != actor.user_id:
                raise Refused("actor_owns")
            if reason not in HANDOFF_REASONS:
                raise Refused("valid_values", f"the reason is one of {', '.join(HANDOFF_REASONS)}")
            order = None
            if reason in _NEEDS_ORDER:
                order = order_id and _one(
                    conn, "SELECT id, status, customer_id FROM orders WHERE id = :id", id=order_id
                )
                if not order or order["customer_id"] != actor.user_id:
                    raise Refused("handoff_reason", "name the customer's order the dispute is about")
            holds, unmet, then = True, "", ""
            tail = _HANDOFF_TAIL  # a yes to an offer the check could not read is the exception
            evidence: dict[str, Any] = {}
            if reason == "shop_decided":
                # The request in front of the agent, not any earlier one: the conversation's latest decision, which
                # refer_to_staff has just recorded when the handoff names an order and units.
                latest = _latest_proposal(conn, conversation_id)
                holds = (
                    latest is not None
                    and (latest["status"], latest["status_reason"]) == ("ineligible", "needs_person")
                    and _out_of_date(conn, latest, now, policy) is None
                )
                evidence["reasons"] = list(latest["reasons"]) if holds else []  # the sections the decision rests on
                unmet = (
                    "the latest refund decision of this conversation, on the order and policy as they are now, is not "
                    "that a staff member takes the case"
                )
                then = (
                    "For a refund request a staff member decides, name its order and units in the handoff: the "
                    "backend records the request when the policy sends it to staff. Otherwise call propose_refund and "
                    "follow its result."
                )
            elif reason == "return_disputed":
                units = list(dict.fromkeys(unit_ids))
                found = (
                    conn.execute(
                        text(
                            "SELECT u.id, (u.received_back_at IS NOT NULL AND u.received_back_at <= :now) AS received, "
                            "EXISTS (SELECT 1 FROM ledger_lines l WHERE l.order_unit_id = u.id) AS refunded "
                            "FROM order_units u WHERE u.order_id = :order AND u.id = ANY(:units) ORDER BY u.id"
                        ),
                        {"now": now, "order": order["id"], "units": units},
                    )
                    .mappings()
                    .all()
                )
                if not units or len(found) != len(units):
                    raise Refused("handoff_reason", "name the units of that order the customer says were sent")
                if order["status"] != "delivered":
                    holds, unmet = False, "that order is not recorded as delivered"
                    then = f"Tell the customer its status ({policy.citation('eligible-orders')})."
                else:
                    settled = [unit["id"] for unit in found if unit["received"] or unit["refunded"]]
                    holds = not settled
                    unmet = f"the records show {', '.join(settled)} received back or already refunded"
                    then = (
                        "A unit received back is requested with propose_refund; a refunded unit is reported with its "
                        f"receipt ({policy.citation('remaining')})."
                    )
            elif reason == "shipping_refund":
                found, unmet = request_for_shipping_refund(_written(conn, conversation_id), customer_words)
                holds = found is not None
                evidence["customer_message"] = found
                then = (
                    f"Answer a question about shipping from ({policy.citation('shipping')}): shipping is never "
                    "refunded automatically, and a staff member takes a request to refund it. If the customer wants "
                    f"the shipping charge refunded, ask them: {SHIPPING_OFFER} Hand off with shipping_refund only "
                    "after their yes to that question, copying the yes. Meanwhile go on with the refund of any item "
                    "the customer asked for."
                )
                tail = ""
            elif reason == "customer_asked":
                request = request_for_person(_written(conn, conversation_id), customer_words)
                holds, unmet = request.message_id is not None, request.unmet
                evidence["customer_message"], evidence["basis"] = request.message_id, request.basis
                if unmet == YES_WITHOUT_OFFER:
                    then = (
                        "If you meant to offer a person, ask the customer plainly, for example: Would you like me to "
                        "connect you with a staff member? Their yes to that question is the request; do not ask them "
                        "to word the request again themselves."
                    )
                    tail = ""
                else:
                    then = (
                        "Copy the customer's words that ask for a person exactly. If the customer has not asked for "
                        "one, answer from the policy, and offer a person only where it says to; the customer's yes to "
                        "that offer is a request for one."
                    )
            elif reason == "delivery_disputed":
                holds = order["status"] == "delivered"
                unmet = "that order is not recorded as delivered, so it is on its way, not disputed"
                then = (
                    "Tell the customer its status; cancelling it or changing its delivery is outside this process, so "
                    f"offer a person for that ({policy.citation('eligible-orders')})."
                )
            if not holds:
                raise Refused("handoff_reason", f"{unmet}. {then}{tail}")
    except Refused as refusal:
        _record_rejection(engine, now, actor, "hand_off", refusal, conversation_id=conversation_id)
        raise
    return evidence


def take_handoff(engine: Engine, actor: Actor, handoff_id: str, now: datetime) -> None:
    """A staff member takes an open handoff in the console."""
    try:
        with engine.begin() as conn:
            found = _one(conn, "SELECT conversation_id FROM handoffs WHERE id = :id", id=handoff_id)
            user = _one(conn, "SELECT role FROM users WHERE id = :id", id=actor.user_id)
            if actor.kind != "staff" or user is None or user["role"] != "staff":
                raise Refused("staff_role")
            if found is None:
                raise Refused("invalid_transition", "no such handoff")
            _lock_conversation(conn, found["conversation_id"])
            handoff = _one(conn, "SELECT status FROM handoffs WHERE id = :id FOR UPDATE", id=handoff_id)
            if handoff["status"] != "open":
                raise Refused("invalid_transition", "the handoff is already taken")
            conn.execute(
                text("UPDATE handoffs SET status = 'taken', taken_by = :staff, taken_at = :now WHERE id = :id"),
                {"staff": actor.user_id, "now": now, "id": handoff_id},
            )
            _audit(
                conn,
                at=now,
                actor_type="staff",
                actor_id=actor.user_id,
                event="take_handoff",
                outcome="committed",
                conversation_id=found["conversation_id"],
                details={"handoff_id": handoff_id},
            )
    except Refused as refusal:
        _record_rejection(engine, now, actor, "take_handoff", refusal)
        raise


# Execute


@dataclass
class _Execution:
    conn: Connection
    actor: Actor
    conversation: RowMapping | None
    proposal: RowMapping | None
    now: datetime
    policy: Policy
    idempotency_key: str
    request_hash: str
    origin: str  # the conversation the agent's call came from
    units: list[RowMapping] = field(default_factory=list)


def _approval(x: _Execution) -> RowMapping | None:
    return _one(
        x.conn,
        "SELECT id, content_hash FROM staff_decisions WHERE proposal_id = :id AND decision = 'approved'",
        id=x.proposal["id"],
    )


def _check_actor_owns(x: _Execution) -> None:
    p, c = x.proposal, x.conversation
    if x.actor.kind != "agent" or p is None or c is None or p["customer_id"] != x.actor.user_id:
        raise Refused("actor_owns")
    if c["customer_id"] != x.actor.user_id:
        raise Refused("actor_owns")


def _check_request_key_consistent(x: _Execution) -> dict | None:
    op = _one(
        x.conn,
        "SELECT request_hash, receipt FROM refund_operations WHERE idempotency_key = :key",
        key=x.idempotency_key,
    )
    if op is None:
        return None
    if op["request_hash"] != x.request_hash:
        raise Refused("request_key_consistent", "the same key was used for another request")
    return op["receipt"]


def _check_first_execution(x: _Execution) -> dict | None:
    op = _one(x.conn, "SELECT receipt FROM refund_operations WHERE proposal_id = :id", id=x.proposal["id"])
    return None if op is None else op["receipt"]


def _check_same_conversation(x: _Execution) -> None:
    # A request made in another conversation of the customer is paid from there: a handoff here must stop this agent,
    # and the lock taken is the proposal's conversation, so both have to be the same row (INV-8).
    if x.proposal["conversation_id"] != x.origin:
        raise Refused("same_conversation", "the proposal belongs to another conversation")


def _check_agent_in_control(x: _Execution) -> None:
    if x.conversation["control"] != "agent":
        raise Refused("agent_in_control")


def _check_valid_values(x: _Execution) -> None:
    p = x.proposal
    x.units = _all(
        x.conn,
        "SELECT pu.order_unit_id, pu.amount_minor, u.paid_minor, u.order_id, u.received_back_at "
        "FROM proposal_units pu JOIN order_units u ON u.id = pu.order_unit_id "
        "WHERE pu.proposal_id = :id ORDER BY pu.order_unit_id",
        id=p["id"],
    )
    payment = _one(x.conn, "SELECT order_id FROM payments WHERE id = :id", id=p["payment_id"])
    valid = (
        bool(x.units)
        and payment is not None
        and payment["order_id"] == p["order_id"]
        and p["currency"] == x.policy.currency
        and all(u["amount_minor"] == u["paid_minor"] > 0 and u["order_id"] == p["order_id"] for u in x.units)
        and sum(u["amount_minor"] for u in x.units) == p["amount_minor"] > 0
    )
    if not valid:
        raise Refused("valid_values", "the proposal's amounts, units, currency or payment are not valid")


def _check_status_approved(x: _Execution) -> None:
    if x.proposal["status"] != Status.APPROVED:
        raise Refused("status_approved", f"the proposal is {x.proposal['status']}")


def _check_customer_confirmed(x: _Execution) -> None:
    row = _one(
        x.conn,
        "SELECT content_hash FROM customer_confirmations WHERE proposal_id = :id AND decision = 'confirmed'",
        id=x.proposal["id"],
    )
    if row is None or row["content_hash"] != x.proposal["content_hash"]:
        raise Refused("customer_confirmed")


def _check_staff_approved(x: _Execution) -> None:
    row = _approval(x)
    if row is None or row["content_hash"] != x.proposal["content_hash"]:
        raise Refused("staff_approved")


def _check_approval_used_once(x: _Execution) -> None:
    row = _approval(x)
    if row is not None and _one(x.conn, "SELECT 1 FROM refund_operations WHERE approval_id = :id", id=row["id"]):
        raise Refused("approval_used_once")


def _check_proposal_current(x: _Execution) -> None:
    p = x.proposal
    change = _out_of_date(x.conn, p, x.now, x.policy)
    if change:
        raise Refused("proposal_current", change[1])
    recomputed = proposal_content_hash(
        customer_id=p["customer_id"],
        order_id=p["order_id"],
        units=[(u["order_unit_id"], u["amount_minor"]) for u in x.units],
        amount_minor=p["amount_minor"],
        currency=p["currency"],
        payment_id=p["payment_id"],
        policy_version=p["policy_version"],
        policy_hash=p["policy_hash"],
        order_material_version=p["order_material_version"],
        expires_at=p["expires_at"],
    )
    if recomputed != p["content_hash"]:
        raise Refused("proposal_current", "the stored content does not match its hash")


def _check_within_window(x: _Execution) -> None:
    order = _one(x.conn, "SELECT delivered_at FROM orders WHERE id = :id", id=x.proposal["order_id"])
    delivered = order["delivered_at"]
    if delivered is None or x.proposal["created_at"] > eligibility.refund_deadline(x.policy, delivered):
        raise Refused("within_window")


def _check_order_status_eligible(x: _Execution) -> None:
    order = _one(x.conn, "SELECT status FROM orders WHERE id = :id", id=x.proposal["order_id"])
    if order["status"] not in x.policy.rules.eligible_order_statuses:
        raise Refused("order_status_eligible")


def _check_return_received(x: _Execution) -> None:
    if not all(u["received_back_at"] is not None and u["received_back_at"] <= x.now for u in x.units):
        raise Refused("return_received")


def _check_units_available(x: _Execution) -> None:
    # A friendly early answer; the unique ledger line per unit is what makes it hold under concurrency.
    units = [u["order_unit_id"] for u in x.units]
    if _one(x.conn, "SELECT 1 FROM ledger_lines WHERE order_unit_id = ANY(:units)", units=units):
        raise Refused("units_available")


EXECUTE_CHECKS: dict[str, Callable[[_Execution], dict | None]] = {
    "actor_owns": _check_actor_owns,
    "same_conversation": _check_same_conversation,
    "request_key_consistent": _check_request_key_consistent,
    "first_execution": _check_first_execution,
    "agent_in_control": _check_agent_in_control,
    "valid_values": _check_valid_values,
    "status_approved": _check_status_approved,
    "customer_confirmed": _check_customer_confirmed,
    "staff_approved": _check_staff_approved,
    "approval_used_once": _check_approval_used_once,
    "proposal_current": _check_proposal_current,
    "within_window": _check_within_window,
    "order_status_eligible": _check_order_status_eligible,
    "return_received": _check_return_received,
    "units_available": _check_units_available,
}
_EXECUTE = {"A": next(t for t in TRANSITIONS if t.event == "execute"), "C": LAB_TRANSITIONS[0]}
_CONSTRAINT_CHECKS = {
    "ledger_lines_order_unit_id_key": "units_available",
    "refund_operations_idempotency_key_key": "request_key_consistent",
    "refund_operations_proposal_id_key": "first_execution",
    "refund_operations_approval_id_key": "approval_used_once",
}


def _commit_refund(x: _Execution) -> dict:
    p = x.proposal
    approval = _approval(x)
    number = x.conn.execute(text("SELECT nextval('receipt_numbers')")).scalar_one()
    operation_id = _new_id("op")
    receipt = {
        "receipt_number": f"R-{number:08d}",
        "operation_id": operation_id,
        "proposal_id": p["id"],
        "amount_minor": p["amount_minor"],
        "currency": p["currency"],
        "payment_id": p["payment_id"],
        "units": [{"unit_id": u["order_unit_id"], "amount_minor": u["amount_minor"]} for u in x.units],
        "committed_at": x.now.isoformat(),
    }
    x.conn.execute(
        text(
            "INSERT INTO refund_operations (id, proposal_id, approval_id, approval_decision, idempotency_key, "
            "request_hash, amount_minor, currency, payment_id, receipt_number, receipt, committed_at) VALUES (:id, "
            ":proposal, :approval, :approval_decision, :key, :hash, :amount, :currency, :payment, :number, "
            "CAST(:receipt AS jsonb), :now)"
        ),
        {
            "id": operation_id,
            "proposal": p["id"],
            "approval": approval["id"] if approval else None,
            "approval_decision": "approved" if approval else None,
            "key": x.idempotency_key,
            "hash": x.request_hash,
            "amount": p["amount_minor"],
            "currency": p["currency"],
            "payment": p["payment_id"],
            "number": receipt["receipt_number"],
            "receipt": json.dumps(receipt),
            "now": x.now,
        },
    )
    _reach("ledger", p["id"])  # between the operation and its ledger lines (plan section 13, failure case 7)
    for unit in x.units:
        x.conn.execute(
            text(
                "INSERT INTO ledger_lines (id, operation_id, order_unit_id, amount_minor, currency, payment_id) "
                "VALUES (:id, :operation, :unit, :amount, :currency, :payment)"
            ),
            {
                "id": _new_id("led"),
                "operation": operation_id,
                "unit": unit["order_unit_id"],
                "amount": unit["amount_minor"],
                "currency": p["currency"],
                "payment": p["payment_id"],
            },
        )
    _set_status(x.conn, p["id"], Status.REFUNDED, None)
    _audit(
        x.conn,
        at=x.now,
        actor_type="agent",
        actor_id=x.actor.user_id,
        event="execute",
        outcome="committed",
        conversation_id=p["conversation_id"],
        proposal_id=p["id"],
        operation_id=operation_id,
    )
    return receipt


def execute_for_conversation(
    engine: Engine,
    actor: Actor,
    conversation_id: str,
    idempotency_key: str,
    now: datetime,
    policy: Policy,
    configuration: Configuration = "A",
) -> dict:
    """Pay the conversation's request, which the backend finds: the agent names no proposal (plan change log,
    2026-10-21, v1.1 step 2). In configuration A the request is the conversation's latest proposal that the policy
    did not refuse or send to a person. In C, where the lab removes the policy and status checks, it is the latest
    proposal of any status, so the lab's agent can still reach a refused request, as it could when it named one.
    execute() then makes every check of the configuration as before: in A a request not yet confirmed or approved
    is refused, and a request already paid returns its receipt again. A call that already paid, run again after a
    restart, returns the receipt of what it paid, never a later request of the conversation. An older proposal of
    the conversation is no longer reachable through the tool in either configuration; the authorization table
    reaches it through execute()."""
    with engine.connect() as conn:
        target = _one(
            conn,
            "SELECT proposal_id AS id FROM refund_operations WHERE idempotency_key = :key",
            key=idempotency_key,
        ) or _one(
            conn,
            "SELECT id FROM proposals WHERE conversation_id = :id AND (:lab OR status <> 'ineligible') "
            "ORDER BY created_at DESC, created_xact DESC LIMIT 1",
            id=conversation_id,
            lab=configuration == "C",
        )
    if target is None:
        refusal = Refused("invalid_transition", "this conversation has no refund request to pay")
        _record_rejection(engine, now, actor, "execute", refusal, conversation_id=conversation_id)
        raise refusal
    return execute(
        engine, actor, target["id"], idempotency_key, now, policy, configuration, conversation_id=conversation_id
    )


def execute(
    engine: Engine,
    actor: Actor,
    proposal_id: str,
    idempotency_key: str,
    now: datetime,
    policy: Policy,
    configuration: Configuration = "A",
    *,
    conversation_id: str,
) -> dict:
    """Refund an approved proposal at most once. A retry, with the same key or a new one, returns the stored receipt.

    conversation_id is the conversation the agent's call came from, as the backend knows it (never from the model);
    only a proposal of that conversation can be paid.

    Configuration C exists only in the isolated evaluation harness, on a synthetic database.
    """
    transition = _EXECUTE[configuration]
    try:
        try:
            with engine.begin() as conn:
                conversation, proposal = _lock_proposal(conn, proposal_id)
                x = _Execution(
                    conn,
                    actor,
                    conversation,
                    proposal,
                    now,
                    policy,
                    idempotency_key,
                    _digest({"proposal": proposal_id}),
                    conversation_id,
                )
                for name in transition.checks:
                    stored = EXECUTE_CHECKS[name](x)
                    if stored is not None:
                        return stored
                _reach("execute", proposal_id)
                return _commit_refund(x)
        except IntegrityError as error:
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            raise Refused(
                _CONSTRAINT_CHECKS.get(constraint, "valid_values"), "a concurrent change came first"
            ) from error
    except Refused as refusal:
        _record_rejection(engine, now, actor, "execute", refusal, proposal_id=proposal_id)
        if refusal.check == "proposal_current":
            _close_out_of_date(engine, proposal_id, now, policy)
        raise
