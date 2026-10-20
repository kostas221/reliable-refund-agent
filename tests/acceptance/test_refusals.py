"""What the backend refuses, and that a refusal writes nothing but its audit record (acceptance 2, 8, 10, 11, 12;
failure cases 3, 4, 10 and 12 of plan section 13). Expected values are written by hand.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from refund_agent.fixtures import seed
from refund_agent.refunds import Actor, cancel, confirm, decide, execute, hand_off, propose
from tests.acceptance.flows import DEVELOPMENT, POLICY, approved, attempt, home, proposed, refused_check, rows

NOW = DEVELOPMENT["D01"].now


def seeded(db, scenario_id: str):
    seed(db("owner"), DEVELOPMENT[scenario_id], POLICY)
    return db("app")


# Foreign data (D07: Gabriela is signed in; d07-o2 is Hugo's order)


def test_a_proposal_for_a_foreign_order_creates_nothing(db):
    app = seeded(db, "D07")
    conversation, _ = proposed(app, "d07-gabi", "d07-o1", ["d07-o1-u1"], "own", NOW)  # her own order: a record
    gabi = Actor("agent", "d07-gabi")
    check = refused_check(lambda: propose(app, gabi, conversation, "d07-o2", ["d07-o2-u1"], "foreign", NOW, POLICY))
    assert check == "actor_owns"
    assert rows(app, "SELECT order_id FROM proposals") == [("d07-o1",)]
    assert rows(app, "SELECT event, outcome, reason FROM audit_events WHERE outcome = 'rejected'") == [
        ("propose", "rejected", "actor_owns")
    ]


def test_another_customers_session_gets_no_receipt(db):
    app = seeded(db, "D07")
    hugos = approved(app, "d07-hugo", "d07-rui", "d07-o2", ["d07-o2-u1"], "propose-hugo", NOW)
    assert attempt(app, "d07-hugo", hugos, "execute-hugo", NOW)[0] == "receipt"
    # Gabriela's agent replays Hugo's proposal with Hugo's key: refused, and no receipt comes back.
    assert attempt(app, "d07-gabi", hugos, "execute-hugo", NOW) == ("refused", "actor_owns")
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(1,)]
    assert rows(app, "SELECT actor_id, reason FROM audit_events WHERE outcome = 'rejected'") == [
        ("d07-gabi", "actor_owns")
    ]


# Keys and repeated refunds (D02: bowl u1 6990, plate u2 3490, napkins u3 not returned)


def test_the_same_key_for_another_proposal_is_a_conflict(db):
    app = seeded(db, "D02")
    bowl = approved(app, "d02-bia", "d02-rui", "d02-o1", ["d02-o1-u1"], "propose-bowl", NOW)
    plate = approved(app, "d02-bia", "d02-rui", "d02-o1", ["d02-o1-u2"], "propose-plate", NOW)
    assert attempt(app, "d02-bia", bowl, "execute-k", NOW)[0] == "receipt"
    assert attempt(app, "d02-bia", plate, "execute-k", NOW) == ("refused", "request_key_consistent")
    assert rows(app, "SELECT order_unit_id FROM ledger_lines") == [("d02-o1-u1",)]
    assert rows(app, "SELECT status FROM proposals ORDER BY amount_minor") == [("approved",), ("refunded",)]


def test_a_new_proposal_for_a_refunded_unit_is_refused_by_the_policy(db):
    app = seeded(db, "D01")
    first = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    attempt(app, "d01-ana", first, "execute-1", NOW)
    _, again = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-2", NOW)
    assert (again.status, again.reasons) == ("ineligible", ("remaining",))
    assert rows(app, "SELECT count(*) FROM ledger_lines") == [(1,)]


def test_a_proposal_approved_before_another_refund_of_its_unit_is_refused_at_execution(db):
    app = seeded(db, "D01")
    first = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    second = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-2", NOW)
    assert attempt(app, "d01-ana", first, "execute-1", NOW)[0] == "receipt"
    assert attempt(app, "d01-ana", second, "execute-2", NOW) == ("refused", "units_available")
    assert rows(app, "SELECT count(*) FROM ledger_lines") == [(1,)]


# Invalid arguments write nothing (failure case 12)


@pytest.mark.parametrize(
    "units",
    [[], ["d02-o1-u1", "d02-o1-u1"], ["d02-o1-u9"], ["d01-o1-u1"]],
    ids=["no units", "repeated unit", "unknown unit", "unit of another order"],
)
def test_invalid_units_write_nothing(db, units):
    app = seeded(db, "D02")
    conversation, _ = proposed(app, "d02-bia", "d02-o1", ["d02-o1-u1"], "valid", NOW)
    bia = Actor("agent", "d02-bia")
    check = refused_check(lambda: propose(app, bia, conversation, "d02-o1", units, "invalid", NOW, POLICY))
    assert check == "valid_values"
    assert rows(app, "SELECT count(*) FROM proposals") == [(1,)]


def test_the_same_proposal_key_with_another_request_is_a_conflict(db):
    app = seeded(db, "D02")
    conversation, _ = proposed(app, "d02-bia", "d02-o1", ["d02-o1-u1"], "propose-1", NOW)
    bia = Actor("agent", "d02-bia")
    again = propose(app, bia, conversation, "d02-o1", ["d02-o1-u1"], "propose-1", NOW, POLICY)
    assert again.status == "awaiting_customer_confirmation"  # the same request: the stored proposal
    check = refused_check(lambda: propose(app, bia, conversation, "d02-o1", ["d02-o1-u2"], "propose-1", NOW, POLICY))
    assert check == "request_key_consistent"
    assert rows(app, "SELECT count(*) FROM proposals") == [(1,)]


# One open proposal per conversation


def test_an_unconfirmed_proposal_is_superseded_by_an_eligible_one(db):
    app = seeded(db, "D02")
    conversation, bowl = proposed(app, "d02-bia", "d02-o1", ["d02-o1-u1"], "bowl", NOW)
    _, both = proposed(app, "d02-bia", "d02-o1", ["d02-o1-u1", "d02-o1-u2"], "bowl-and-plate", NOW, conversation)
    assert (both.status, both.amount_minor) == ("awaiting_customer_confirmation", 10480)
    assert rows(app, f"SELECT status, status_reason FROM proposals WHERE id = '{bowl.id}'") == [
        ("invalidated", "superseded")
    ]


def test_a_refused_request_supersedes_nothing(db):
    app = seeded(db, "D02")
    conversation, bowl = proposed(app, "d02-bia", "d02-o1", ["d02-o1-u1"], "bowl", NOW)
    _, napkins = proposed(app, "d02-bia", "d02-o1", ["d02-o1-u3"], "napkins", NOW, conversation)
    assert (napkins.status, napkins.reasons) == ("ineligible", ("return",))
    assert rows(app, f"SELECT status FROM proposals WHERE id = '{bowl.id}'") == [("awaiting_customer_confirmation",)]


def test_a_confirmed_proposal_blocks_a_new_one_in_the_same_conversation(db):
    app = seeded(db, "D02")
    conversation, bowl = proposed(app, "d02-bia", "d02-o1", ["d02-o1-u1"], "bowl", NOW)
    confirm(app, Actor("customer", "d02-bia"), bowl.id, "confirmed", NOW, POLICY)
    bia = Actor("agent", "d02-bia")
    check = refused_check(lambda: propose(app, bia, conversation, "d02-o1", ["d02-o1-u2"], "plate", NOW, POLICY))
    assert check == "no_confirmed_open_proposal"
    assert rows(app, "SELECT status FROM proposals") == [("awaiting_staff_approval",)]


def test_a_new_proposal_after_expiry_closes_the_old_one(db):
    app = seeded(db, "D01")
    conversation, old = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "old", NOW)
    later = NOW + timedelta(hours=73)
    _, new = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "new", later, conversation)
    assert new.status == "awaiting_customer_confirmation"
    assert rows(app, f"SELECT status, status_reason FROM proposals WHERE id = '{old.id}'") == [("expired", "expired")]


# The customer's and the staff member's buttons are theirs alone (acceptance 11)


def test_buttons_refuse_the_wrong_channel(db):
    app = seeded(db, "D01")
    _, proposal = proposed(app, "d01-ana", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    agent, customer = Actor("agent", "d01-ana"), Actor("customer", "d01-ana")
    assert refused_check(lambda: confirm(app, agent, proposal.id, "confirmed", NOW, POLICY)) == "actor_owns"
    assert refused_check(lambda: cancel(app, agent, proposal.id, NOW, POLICY)) == "actor_owns"
    confirm(app, customer, proposal.id, "confirmed", NOW, POLICY)
    for actor in (agent, customer):
        assert refused_check(lambda a=actor: decide(app, a, proposal.id, "approved", NOW, POLICY)) == "staff_role"
    assert rows(app, "SELECT status FROM proposals") == [("awaiting_staff_approval",)]


def test_execute_refuses_a_customer_or_staff_actor(db):
    app = seeded(db, "D01")
    proposal_id = approved(app, "d01-ana", "d01-rui", "d01-o1", ["d01-o1-u1"], "propose-1", NOW)
    for actor in (Actor("customer", "d01-ana"), Actor("staff", "d01-rui")):
        check = refused_check(
            lambda a=actor: execute(
                app, a, proposal_id, "execute-1", NOW, POLICY, conversation_id=home(app, proposal_id)
            )
        )
        assert check == "actor_owns"
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(0,)]


# The database ties an approval to its own proposal (acceptance 10)


def test_an_approval_cannot_pay_for_another_proposal(db):
    app = seeded(db, "D02")
    bowl = approved(app, "d02-bia", "d02-rui", "d02-o1", ["d02-o1-u1"], "propose-bowl", NOW)
    plate = approved(app, "d02-bia", "d02-rui", "d02-o1", ["d02-o1-u2"], "propose-plate", NOW)
    with pytest.raises(DBAPIError, match="foreign key"), app.begin() as conn:
        bowl_approval = conn.execute(
            text("SELECT id FROM staff_decisions WHERE proposal_id = :id"), {"id": bowl}
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO refund_operations (id, proposal_id, approval_id, approval_decision, idempotency_key, "
                "request_hash, amount_minor, currency, payment_id, receipt_number, receipt, committed_at) VALUES "
                "('op-x', :plate, :approval, 'approved', 'k', 'h', 3490, 'BRL', 'd02-o1-p1', 'R-X', '{}', now())"
            ),
            {"plate": plate, "approval": bowl_approval},
        )
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(0,)]


# The time limit's referral for an earlier on-time proposal (policy section window; plan change log, 2026-10-20)


def test_a_late_request_goes_to_a_person_only_for_units_whose_on_time_proposal_lapsed(db):
    app = seeded(db, "D02")  # delivered 8 September 12:00, so the deadline is 8 October 12:00
    bowl, plate = "d02-o1-u1", "d02-o1-u2"
    proposed(app, "d02-bia", "d02-o1", [bowl], "bowl", NOW)  # left alone: it lapses after 72 hours, still open
    replaced, _ = proposed(app, "d02-bia", "d02-o1", [plate], "plate", NOW)
    proposed(app, "d02-bia", "d02-o1", [bowl], "bowl-instead", NOW, replaced)  # the customer replaced the plate
    handed, _ = proposed(app, "d02-bia", "d02-o1", [plate], "plate-again", NOW)
    hand_off(app, Actor("agent", "d02-bia"), handed, "the customer asked for a person", NOW, origin="customer")
    late = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)  # a day after the deadline
    decisions = {
        name: proposed(app, "d02-bia", "d02-o1", units, f"late-{name}", late)[1]
        for name, units in (("bowl", [bowl]), ("plate", [plate]), ("both", [bowl, plate]))
    }
    assert {name: (p.outcome, p.reasons) for name, p in decisions.items()} == {
        "bowl": ("needs_person", ("window",)),
        "plate": ("refused", ("window",)),  # replaced by the customer, then closed by a handoff: neither counts
        "both": ("refused", ("window",)),  # the plate has no such proposal
    }
