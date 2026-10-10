"""Races on a real PostgreSQL, with separate connections (plan section 13, failure cases 1 and 2; acceptance 6 and 7).

The failpoint refunds.before_commit holds transactions after all their checks have passed and before they write,
so the database, not the order in which Python happened to run, has to keep a unit from being refunded twice.
Expected values are written by hand.
"""

import threading
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from refund_agent import refunds
from refund_agent.fixtures import seed
from refund_agent.policy import load_policy
from refund_agent.refunds import Actor, Refused, confirm, decide, execute, open_conversation, propose
from refund_agent.scenarios import SPLIT_DIRS, Scenario, load_split

POLICY = load_policy()
DEVELOPMENT = {s.id: s for s in load_split("development")}


def approved(app, customer: str, staff: str, order: str, units: list[str], key: str, now: datetime) -> str:
    """A proposal in a new conversation of `customer`, confirmed and approved."""
    conversation = open_conversation(app, Actor("customer", customer), now)
    proposal = propose(app, Actor("agent", customer), conversation, order, units, key, now, POLICY)
    confirm(app, Actor("customer", customer), proposal.id, "confirmed", now, POLICY)
    decide(app, Actor("staff", staff), proposal.id, "approved", now, POLICY)
    return proposal.id


def attempt(app, customer: str, proposal_id: str, key: str, now: datetime):
    try:
        return "receipt", execute(app, Actor("agent", customer), proposal_id, key, now, POLICY)
    except Refused as refused:
        return "refused", refused.check


def rows(app, sql):
    with app.connect() as conn:
        return [tuple(row) for row in conn.execute(text(sql))]


def run_together(calls):
    with ThreadPoolExecutor(len(calls)) as pool:
        return [future.result(timeout=30) for future in [pool.submit(call) for call in calls]]


def test_two_proposals_for_the_same_unit_refund_it_once(db, monkeypatch):
    scenario = DEVELOPMENT["D01"]
    seed(db("owner"), scenario, POLICY)
    app = db("app")
    now = scenario.now
    first = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-a", now)
    second = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-b", now)

    # Both transactions pass every check before either writes.
    both_checked = threading.Barrier(2, timeout=10)
    monkeypatch.setattr(refunds, "before_commit", lambda proposal_id: both_checked.wait())
    outcomes = run_together([lambda p=p: attempt(app, "d01-ana", p, f"execute-{p}", now) for p in (first, second)])

    assert sorted(kind for kind, _ in outcomes) == ["receipt", "refused"]
    assert [value for kind, value in outcomes if kind == "refused"] == ["units_available"]
    assert rows(app, "SELECT order_unit_id, amount_minor FROM ledger_lines") == [("d01-o1-u1", 4990)]
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(1,)]


def test_two_connections_executing_one_approval_commit_one_refund(db, monkeypatch):
    scenario = DEVELOPMENT["D01"]
    seed(db("owner"), scenario, POLICY)
    app = db("app")
    now = scenario.now
    proposal = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-a", now)

    # The first transaction stays open after its checks; the second arrives while it is open, with another key.
    first_inside = threading.Event()

    def hold(proposal_id):
        first_inside.set()
        time.sleep(0.5)

    monkeypatch.setattr(refunds, "before_commit", hold)

    def second():
        first_inside.wait(10)
        return attempt(app, "d01-ana", proposal, "execute-2", now)

    first_outcome, second_outcome = run_together([lambda: attempt(app, "d01-ana", proposal, "execute-1", now), second])

    assert first_outcome[0] == second_outcome[0] == "receipt"
    assert first_outcome[1] == second_outcome[1]
    assert rows(app, "SELECT count(*), CAST(sum(amount_minor) AS bigint) FROM refund_operations") == [(1, 4990)]
    assert rows(app, "SELECT count(*) FROM ledger_lines") == [(1,)]


def test_different_units_of_the_same_product_both_refund(db, monkeypatch):
    # D03 with its third glass also returned: units u2 (3323) and u3 (3324) can both be refunded; u1 was before.
    path = SPLIT_DIRS["development"] / "D03-identical-units-after-earlier-refund.toml"
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    raw["fixture"]["orders"][0]["units"][2]["received_back_at"] = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    scenario = Scenario.model_validate(raw)
    seed(db("owner"), scenario, POLICY)
    app = db("app")
    now = scenario.now
    second_glass = approved(app, "d03-caio", "d03-rui", "d03-o1", ["d03-o1-u2"], "propose-u2", now)
    third_glass = approved(app, "d03-caio", "d03-rui", "d03-o1", ["d03-o1-u3"], "propose-u3", now)

    both_checked = threading.Barrier(2, timeout=10)
    monkeypatch.setattr(refunds, "before_commit", lambda proposal_id: both_checked.wait())
    later = now + timedelta(minutes=1)
    outcomes = run_together(
        [lambda p=p: attempt(app, "d03-caio", p, f"execute-{p}", later) for p in (second_glass, third_glass)]
    )

    assert [kind for kind, _ in outcomes] == ["receipt", "receipt"]
    assert rows(app, "SELECT order_unit_id, amount_minor FROM ledger_lines ORDER BY order_unit_id") == [
        ("d03-o1-u1", 3323),
        ("d03-o1-u2", 3323),
        ("d03-o1-u3", 3324),
    ]
