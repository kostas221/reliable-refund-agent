"""Pure policy decisions: no database, no clock of their own, no model.

The backend calls these inside its transactions with data it read itself; tests call them directly. Every
reason they return is the ID of the policy section that decides it, so a reason is also its citation.
All times must be aware UTC datetimes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from refund_agent.policy import Policy

# Olist payment_type values that name a payment method ("not_defined" does not).
PAYMENT_METHODS = frozenset({"credit_card", "boleto", "voucher", "debit_card"})

# Where each policy section is enforced. A test checks that every section of the policy appears here.
ENFORCED_BY = {
    "scope": "the currency check of valid_values; the UTC check of every function here",
    "eligible-orders": "evaluate()",
    "window": "evaluate() with refund_deadline()",
    "return": "evaluate()",
    "amount": "split_paid() once when the order is recorded; evaluate() adds up the units' paid amounts",
    "remaining": "evaluate(); at execution a unique constraint allows one ledger line per unit",
    "shipping": "amounts never include shipping; a request for shipping goes to a person through the agent",
    "payment": "evaluate() with single_valid_payment()",
    "approval": "the state machine checks customer_confirmed and staff_approved",
    "validity": "proposal_expires_at() and proposal_active(); the state machine check proposal_current",
    "payout": "a summary of the sections above, enforced by the checks of the execute transition",
    "exceptions": "the agent's request_handoff tool, and every needs_person decision",
}


class Outcome(StrEnum):
    ELIGIBLE = "eligible"
    REFUSED = "refused"
    NEEDS_PERSON = "needs_person"


@dataclass(frozen=True)
class Payment:
    method: str
    amount_minor: int


@dataclass(frozen=True)
class Unit:
    id: str
    paid_minor: int
    received_back: bool
    refunded: bool


@dataclass(frozen=True)
class Order:
    status: str
    purchased_at: datetime
    delivered_at: datetime | None
    payments: tuple[Payment, ...]
    units: tuple[Unit, ...]


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reasons: tuple[str, ...]  # policy section IDs; empty when eligible
    amount_minor: int  # the refund for the requested units when eligible, otherwise 0


def _require_utc(moment: datetime, name: str) -> None:
    if moment.tzinfo is None or moment.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an aware UTC datetime, got {moment!r}")


def refund_deadline(policy: Policy, delivered_at: datetime) -> datetime:
    """The last moment a refund can be requested. A request at exactly this moment is on time."""
    _require_utc(delivered_at, "delivered_at")
    return delivered_at + timedelta(days=policy.rules.refund_window_days)


def proposal_expires_at(policy: Policy, created_at: datetime) -> datetime:
    _require_utc(created_at, "created_at")
    return created_at + timedelta(hours=policy.rules.proposal_ttl_hours)


def proposal_active(expires_at: datetime, now: datetime) -> bool:
    """A proposal can be confirmed, approved or paid only strictly before it expires."""
    _require_utc(expires_at, "expires_at")
    _require_utc(now, "now")
    return now < expires_at


def split_paid(total_minor: int, units: int) -> list[int]:
    """Split a paid total among identical units, once, when the order is recorded.

    Each unit gets the total divided by the number of units, rounded down, and the leftover goes one minor unit
    at a time to the last units: 1001 over 2 units is [500, 501]; 1001 over 3 units is [333, 334, 334]. Giving
    the whole leftover to the last unit could pay it more than its price (1499 over 3 units of 500 would be
    [499, 499, 501]); spread one at a time, no share exceeds the price when the total is at most units x price.
    """
    if units < 1 or total_minor < 0:
        raise ValueError(f"cannot split {total_minor} over {units} units")
    share, leftover = divmod(total_minor, units)
    return [share] * (units - leftover) + [share + 1] * leftover


def single_valid_payment(order: Order) -> bool:
    """Exactly one payment record, with a known method and a positive amount."""
    return (
        len(order.payments) == 1 and order.payments[0].method in PAYMENT_METHODS and order.payments[0].amount_minor > 0
    )


def _delivery_time_plausible(order: Order, at: datetime) -> bool:
    if order.delivered_at is None:
        return False
    _require_utc(order.delivered_at, "delivered_at")
    return order.purchased_at <= order.delivered_at <= at


def evaluate(
    policy: Policy,
    order: Order,
    unit_ids: tuple[str, ...],
    at: datetime,
    *,
    earlier_request_on_time: bool = False,
) -> Decision:
    """The policy decision for refunding these units of the order, requested at the moment `at`.

    earlier_request_on_time: the backend found an earlier proposal for any of these units that was created
    within the window and then expired or was invalidated before it was paid.

    A refusal wins over a referral to a person: nobody needs to review a request the policy refuses anyway.
    Invalid input (no units, repeated units, units of another order) is an error, not a policy decision.
    """
    _require_utc(at, "at")
    _require_utc(order.purchased_at, "purchased_at")
    if not unit_ids or len(set(unit_ids)) != len(unit_ids):
        raise ValueError(f"unit_ids must be non-empty and distinct, got {unit_ids!r}")
    units = {unit.id: unit for unit in order.units}
    unknown = [unit_id for unit_id in unit_ids if unit_id not in units]
    if unknown:
        raise ValueError(f"units not in this order: {unknown}")
    requested = [units[unit_id] for unit_id in unit_ids]

    refused: list[str] = []
    needs_person: list[str] = []
    if order.status not in policy.rules.eligible_order_statuses:
        refused.append("eligible-orders")
    elif not _delivery_time_plausible(order, at):
        needs_person.append("eligible-orders")
    elif at > refund_deadline(policy, order.delivered_at):
        (needs_person if earlier_request_on_time else refused).append("window")
    if any(unit.refunded for unit in requested):
        refused.append("remaining")
    if not all(unit.received_back for unit in requested):
        refused.append("return")
    if not single_valid_payment(order):
        needs_person.append("payment")

    if refused:
        return Decision(Outcome.REFUSED, tuple(refused), 0)
    if needs_person:
        return Decision(Outcome.NEEDS_PERSON, tuple(needs_person), 0)
    return Decision(Outcome.ELIGIBLE, (), sum(unit.paid_minor for unit in requested))
