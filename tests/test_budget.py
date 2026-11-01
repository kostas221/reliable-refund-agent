"""The budget shared by calls that run at the same time (refund_agent/agent/costs.py): in the live server a customer's
message and a staff decision delivered from the background draw on one budget (outside critique of 2026-11-01)."""

import threading

import pytest

from refund_agent.agent.costs import Budget, BudgetExceeded


def test_two_attempts_in_flight_cannot_pass_the_limit_together():
    budget = Budget(limit_usd=1.0)
    budget.reserve(0.6)  # sent, not yet settled
    with pytest.raises(BudgetExceeded, match=r"\$0\.6000 held by requests in flight"):
        budget.reserve(0.6)
    budget.settle("agent", 0.1, reserved=0.6)  # it cost less than its worst case: the rest is free again
    budget.reserve(0.6)
    assert budget.spent_usd == pytest.approx(0.1)
    assert budget.held_usd == pytest.approx(0.6)
    assert budget.left_usd == pytest.approx(0.3)


def test_threads_racing_for_the_last_room_let_exactly_one_through():
    budget = Budget(limit_usd=1.0)
    start, passed = threading.Barrier(16), []

    def attempt():
        start.wait()
        try:
            budget.reserve(0.6)
            passed.append(True)
        except BudgetExceeded:
            pass

    threads = [threading.Thread(target=attempt) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(passed) == 1


def test_every_settled_attempt_is_handed_to_the_record():
    kept = []
    budget = Budget(limit_usd=1.0, record=lambda role, usd, uncertain: kept.append((role, usd, uncertain)))
    budget.reserve(0.2)
    budget.settle("agent", 0.05, reserved=0.2)
    budget.reserve(0.2)
    budget.settle("agent", 0.2, uncertain=True, reserved=0.2)  # a timeout: its worst case, uncertain
    assert kept == [("agent", 0.05, False), ("agent", 0.2, True)]
    assert budget.held_usd == 0


def test_a_budget_started_from_what_was_spent_before_goes_on_from_there():
    budget = Budget(limit_usd=1.0, spent_usd=0.9)
    with pytest.raises(BudgetExceeded):
        budget.reserve(0.2)


def test_the_latest_stop_is_remembered_until_an_attempt_is_sent():
    budget = Budget(limit_usd=0.1)
    with pytest.raises(BudgetExceeded):
        budget.reserve(0.2)
    assert "over the limit of $0.10" in budget.last_stop
    budget.reserve(0.05)
    assert budget.last_stop is None
    budget.refused_for_credit("the provider refused the request: no credit left")
    assert budget.last_stop == "the provider refused the request: no credit left"


def test_an_overrun_stops_everything_after_it():
    budget = Budget(limit_usd=1.0)
    budget.reserve(0.1)
    budget.settle("agent", 0.2, reserved=0.1)
    with pytest.raises(BudgetExceeded, match="more than its worst case"):
        budget.reserve(0.01)
    assert budget.held_usd == 0
