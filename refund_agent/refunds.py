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
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import Connection, Engine, RowMapping, text
from sqlalchemy.exc import IntegrityError

from refund_agent import eligibility
from refund_agent.policy import Policy
from refund_agent.states import LAB_TRANSITIONS, OPEN, TRANSITIONS, Status

Configuration = Literal["A", "C"]
OPEN_STATUSES = [status.value for status in OPEN]


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


def _earlier_request_on_time(conn: Connection, policy: Policy, delivered_at: datetime | None, units: list[str]) -> bool:
    """An earlier proposal for any of these units was created in time and then expired or was invalidated."""
    if delivered_at is None:
        return False
    return bool(
        conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM proposals p JOIN proposal_units pu ON pu.proposal_id = p.id "
                "WHERE pu.order_unit_id = ANY(:units) AND p.status IN ('expired', 'invalidated') "
                "AND p.created_at <= :deadline)"
            ),
            {"units": units, "deadline": eligibility.refund_deadline(policy, delivered_at)},
        ).scalar_one()
    )


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
) -> ProposalResult:
    """Store a proposal for these units with the amount the backend computes, eligible or not.

    Checks in the order of the propose transition: actor_owns, agent_in_control, request_key_consistent,
    valid_values, then (for an eligible request) no_confirmed_open_proposal and policy_eligible.
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
            earlier = _earlier_request_on_time(conn, policy, order["delivered_at"], list(unit_ids))
            decision = eligibility.evaluate(policy, policy_order, tuple(unit_ids), now, earlier_request_on_time=earlier)
            eligible = decision.outcome is eligibility.Outcome.ELIGIBLE
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
        _record_rejection(engine, now, actor, "propose", refusal, conversation_id=conversation_id)
        raise


# Customer and staff decisions


def confirm(
    engine: Engine,
    actor: Actor,
    proposal_id: str,
    decision: Literal["confirmed", "declined"],
    now: datetime,
    policy: Policy,
) -> str:
    """The customer's button on the proposal card. Only a proposal ID and a decision come in (INV-2)."""
    pending: Refused | None = None
    try:
        with engine.begin() as conn:
            _, proposal = _lock_proposal(conn, proposal_id)
            if actor.kind != "customer" or proposal is None or proposal["customer_id"] != actor.user_id:
                raise Refused("actor_owns")
            if proposal["status"] != Status.AWAITING_CUSTOMER_CONFIRMATION:
                raise Refused("invalid_transition", f"the proposal is {proposal['status']}")
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
) -> str:
    """The staff member's approval or rejection. An approval never overrides the policy (INV-5)."""
    pending: Refused | None = None
    try:
        with engine.begin() as conn:
            _, proposal = _lock_proposal(conn, proposal_id)
            user = _one(conn, "SELECT role FROM users WHERE id = :id", id=actor.user_id)
            if actor.kind != "staff" or user is None or user["role"] != "staff":
                raise Refused("staff_role")
            if proposal is None or proposal["status"] != Status.AWAITING_STAFF_APPROVAL:
                raise Refused("invalid_transition", "the proposal is not awaiting a staff decision")
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
                        "INSERT INTO staff_decisions (id, proposal_id, staff_id, decision, content_hash, decided_at) "
                        "VALUES (:id, :proposal, :staff, :decision, :hash, :now)"
                    ),
                    {
                        "id": decision_id,
                        "proposal": proposal_id,
                        "staff": actor.user_id,
                        "decision": decision,
                        "hash": proposal["content_hash"],
                        "now": now,
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


def cancel(engine: Engine, actor: Actor, proposal_id: str, now: datetime, policy: Policy) -> str:
    """The customer cancels an open proposal, before or after confirming, as long as it is not refunded.

    A proposal that has already expired or become invalid is closed with that status instead: either way no money
    moves, which is what the customer asked for.
    """
    try:
        with engine.begin() as conn:
            _, proposal = _lock_proposal(conn, proposal_id)
            if actor.kind != "customer" or proposal is None or proposal["customer_id"] != actor.user_id:
                raise Refused("actor_owns")
            if proposal["status"] not in OPEN_STATUSES:
                raise Refused("invalid_transition", f"the proposal is {proposal['status']}")
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
