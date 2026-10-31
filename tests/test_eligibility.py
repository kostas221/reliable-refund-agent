"""Behaviour of the refund policy. Expected values are worked out by hand, not taken from the code."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from refund_agent.eligibility import (
    ENFORCED_BY,
    Order,
    Outcome,
    Payment,
    Unit,
    evaluate,
    proposal_active,
    proposal_expires_at,
    refund_deadline,
    split_paid,
    window_deadline,
)
from refund_agent.policy import load_policy

POLICY = load_policy()

# Delivered 2026-09-05 12:00 UTC, so the 30-day deadline is 2026-10-05 12:00 UTC.
ORDER = Order(
    status="delivered",
    purchased_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    delivered_at=datetime(2026, 9, 5, 12, 0, tzinfo=UTC),
    payments=(Payment("credit_card", 2501),),
    units=(
        Unit("u1", paid_minor=1000, received_back=True, refunded=False),
        Unit("u2", paid_minor=1001, received_back=True, refunded=False),
        Unit("u3", paid_minor=500, received_back=False, refunded=False),
    ),
)
AT = datetime(2026, 9, 20, 0, 0, tzinfo=UTC)
DEADLINE = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def decide(order=ORDER, unit_ids=("u1", "u2"), at=AT, **kwargs):
    return evaluate(POLICY, order, unit_ids, at, **kwargs)


def with_units(*units):
    return replace(ORDER, units=units)


def test_eligible_request_refunds_what_was_paid_for_the_units():
    decision = decide()
    assert (decision.outcome, decision.reasons, decision.amount_minor) == (Outcome.ELIGIBLE, (), 2001)


# Time window


def test_deadline_is_thirty_days_of_twenty_four_hours_after_delivery():
    assert refund_deadline(POLICY, ORDER.delivered_at) == DEADLINE


def test_deadline_counts_days_not_calendar_months():
    # 2026 is not a leap year: 27 February + 30 days is 29 March.
    delivered = datetime(2026, 2, 27, 10, 0, tzinfo=UTC)
    assert refund_deadline(POLICY, delivered) == datetime(2026, 3, 29, 10, 0, tzinfo=UTC)


def test_request_exactly_at_the_deadline_is_on_time():
    assert decide(at=DEADLINE).outcome is Outcome.ELIGIBLE


def test_request_one_second_after_the_deadline_is_refused():
    decision = decide(at=DEADLINE + timedelta(seconds=1))
    assert (decision.outcome, decision.reasons) == (Outcome.REFUSED, ("window",))


def test_late_request_after_an_earlier_on_time_proposal_goes_to_a_person():
    decision = decide(at=DEADLINE + timedelta(days=2), earlier_on_time_units=frozenset({"u1", "u2"}))
    assert (decision.outcome, decision.reasons) == (Outcome.NEEDS_PERSON, ("window",))


def test_an_earlier_on_time_proposal_counts_only_for_its_own_units():
    # Only u1 had one (plan change log, 2026-10-20): u2 is simply late, and the refusal wins for the request.
    decision = decide(at=DEADLINE + timedelta(days=2), earlier_on_time_units=frozenset({"u1"}))
    assert (decision.outcome, decision.reasons) == (Outcome.REFUSED, ("window",))


# The deadline the agent's order list shows (v1.3 repair 1, plan change log 2026-10-31): H255's agent read only the
# list, which gave the delivery date and no deadline, and said a unit sent back later could still be refunded.


def test_the_window_shows_its_deadline_only_where_it_decides():
    assert window_deadline(POLICY, "delivered", ORDER.purchased_at, ORDER.delivered_at, AT) == DEADLINE
    assert window_deadline(POLICY, "shipped", ORDER.purchased_at, ORDER.delivered_at, AT) is None  # refused first
    assert window_deadline(POLICY, "delivered", ORDER.purchased_at, None, AT) is None  # a person takes the case
    early = ORDER.purchased_at - timedelta(days=1)
    assert window_deadline(POLICY, "delivered", ORDER.purchased_at, early, AT) is None  # before the purchase
    later = AT + timedelta(seconds=1)
    assert window_deadline(POLICY, "delivered", ORDER.purchased_at, later, AT) is None  # after the request


@pytest.mark.parametrize(
    "order",
    [
        ORDER,
        replace(ORDER, status="shipped"),
        replace(ORDER, delivered_at=None),
        replace(ORDER, delivered_at=datetime(2026, 9, 25, 0, 0, tzinfo=UTC)),  # after some of the moments below
    ],
)
@pytest.mark.parametrize("seconds", [-86_400, -1, 0, 1, 86_400])
def test_a_deadline_shown_as_passed_is_one_the_decision_applies(order, seconds):
    # The list must never show a second, simpler rule: at every moment, a shown deadline has passed exactly when the
    # decision brings in the window section for a unit nothing else refuses.
    for at in (DEADLINE + timedelta(seconds=seconds), AT + timedelta(seconds=seconds)):
        deadline = window_deadline(POLICY, order.status, order.purchased_at, order.delivered_at, at)
        reasons = decide(order=order, unit_ids=("u1",), at=at).reasons
        assert (deadline is not None and at > deadline) == ("window" in reasons), (order.status, at)


def test_a_refusal_wins_over_a_referral_to_a_person():
    # Late but with an earlier on-time proposal, and u3 never came back: the return rule refuses anyway.
    decision = decide(unit_ids=("u3",), at=DEADLINE + timedelta(days=2), earlier_on_time_units=frozenset({"u3"}))
    assert (decision.outcome, decision.reasons) == (Outcome.REFUSED, ("return",))


# A unit with nothing paid (policy section amount; plan change log, 2026-10-20)


def test_a_unit_with_nothing_paid_is_refused_for_its_amount():
    gift = Unit("gift", paid_minor=0, received_back=True, refunded=False)
    order = with_units(*ORDER.units, gift)
    alone, mixed = decide(order, ("gift",)), decide(order, ("u1", "gift"))
    assert (alone.outcome, alone.reasons, alone.amount_minor) == (Outcome.REFUSED, ("amount",), 0)
    assert (mixed.outcome, mixed.reasons, mixed.amount_minor) == (Outcome.REFUSED, ("amount",), 0)
    assert decide(order, ("u1",)).amount_minor == 1000  # the paid unit alone is refunded as before


# Order status and delivery time


def test_order_that_is_not_delivered_is_refused():
    decision = decide(order=replace(ORDER, status="shipped"))
    assert (decision.outcome, decision.reasons) == (Outcome.REFUSED, ("eligible-orders",))


@pytest.mark.parametrize(
    "delivered_at",
    [
        None,
        datetime(2026, 8, 31, 10, 0, tzinfo=UTC),  # before the purchase
        datetime(2026, 9, 21, 0, 0, tzinfo=UTC),  # after the moment of the request
    ],
)
def test_delivered_order_without_a_plausible_delivery_time_goes_to_a_person(delivered_at):
    decision = decide(order=replace(ORDER, delivered_at=delivered_at))
    assert (decision.outcome, decision.reasons) == (Outcome.NEEDS_PERSON, ("eligible-orders",))


# Units


def test_unit_not_received_back_is_refused():
    decision = decide(unit_ids=("u1", "u3"))
    assert (decision.outcome, decision.reasons) == (Outcome.REFUSED, ("return",))


def test_unit_already_refunded_is_refused():
    order = with_units(Unit("u1", 1000, received_back=True, refunded=True), *ORDER.units[1:])
    decision = decide(order=order, unit_ids=("u1",))
    assert (decision.outcome, decision.reasons) == (Outcome.REFUSED, ("remaining",))


def test_the_remaining_units_are_still_eligible():
    order = with_units(Unit("u1", 1000, received_back=True, refunded=True), *ORDER.units[1:])
    decision = decide(order=order, unit_ids=("u2",))
    assert (decision.outcome, decision.amount_minor) == (Outcome.ELIGIBLE, 1001)


@pytest.mark.parametrize("unit_ids", [(), ("u1", "u1"), ("u1", "someone-elses-unit")])
def test_invalid_unit_selection_is_an_error_not_a_decision(unit_ids):
    with pytest.raises(ValueError):
        decide(unit_ids=unit_ids)


# Payments


@pytest.mark.parametrize(
    "payments",
    [
        (),
        (Payment("credit_card", 1500), Payment("credit_card", 1001)),  # two payments of the same method
        (Payment("credit_card", 2000), Payment("voucher", 501)),
        (Payment("not_defined", 2501),),
        (Payment("credit_card", 0),),
    ],
)
def test_anything_but_one_valid_payment_goes_to_a_person(payments):
    decision = decide(order=replace(ORDER, payments=payments))
    assert (decision.outcome, decision.reasons) == (Outcome.NEEDS_PERSON, ("payment",))


@pytest.mark.parametrize("method", ["credit_card", "boleto", "voucher", "debit_card"])
def test_one_valid_payment_of_any_known_method_is_eligible(method):
    assert decide(order=replace(ORDER, payments=(Payment(method, 2501),))).outcome is Outcome.ELIGIBLE


# Splitting a paid total among identical units


@pytest.mark.parametrize(
    ("total", "units", "shares"),
    [
        (1001, 2, [500, 501]),
        (1001, 3, [333, 334, 334]),
        (1499, 3, [499, 500, 500]),
        (1000, 1, [1000]),
        (0, 2, [0, 0]),
    ],
)
def test_split_rounds_down_and_spreads_the_leftover_over_the_last_units(total, units, shares):
    assert split_paid(total, units) == shares


def test_split_never_loses_or_creates_money():
    for total in range(0, 200):
        for units in range(1, 12):
            shares = split_paid(total, units)
            assert sum(shares) == total and len(shares) == units and min(shares) >= 0


def test_no_unit_is_paid_more_than_its_price():
    # Identical units at `price`, with any discount from none to all of it.
    for price in range(0, 40):
        for units in range(1, 9):
            for discount in range(0, units * price + 1):
                assert max(split_paid(units * price - discount, units)) <= price


@pytest.mark.parametrize(("total", "units"), [(100, 0), (-1, 2)])
def test_split_rejects_impossible_input(total, units):
    with pytest.raises(ValueError):
        split_paid(total, units)


# Proposal validity


def test_proposal_expires_seventy_two_hours_after_creation():
    created = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    assert proposal_expires_at(POLICY, created) == datetime(2026, 9, 23, 9, 0, tzinfo=UTC)


def test_proposal_can_be_acted_on_only_strictly_before_expiry():
    expires = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)
    assert proposal_active(expires, expires - timedelta(seconds=1))
    assert not proposal_active(expires, expires)


# Time zones


@pytest.mark.parametrize(
    "moment",
    [datetime(2026, 9, 20, 0, 0), datetime(2026, 9, 20, 3, 0, tzinfo=timezone(timedelta(hours=3)))],
)
def test_times_must_be_utc(moment):
    with pytest.raises(ValueError):
        decide(at=moment)


# Every policy section is enforced somewhere


def test_every_policy_section_says_where_it_is_enforced():
    assert set(ENFORCED_BY) == {section.id for section in POLICY.sections}
