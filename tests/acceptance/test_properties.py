"""Random sequences of actions on the real backend and PostgreSQL, with the invariants checked after every step (plan
section 13: stateful property tests; product contract section 4).

Each sequence starts from a shop somewhere along the way (two conversations per customer, each empty or with a
proposal of returned units taken honestly up to a drawn stage), then Hypothesis draws the rightful actions, by the
person whose action it is: propose, confirm or decline, decide, pay now or late, cancel, ask for a person, time
passing. Keys come from small pools, so retries and reused keys happen, and some actions come exactly when a proposal
expires or a minute before, the edge of "strictly before it expires".

After every step, written here by hand and never with the backend's code:
- one probe, each kind in turn, tries what must be refused in the state reached, and checks it is refused for the
  right reason: another customer or another conversation paying, confirming, cancelling, proposing or handing off; a
  customer deciding as staff; cancelling a closed proposal; proposing after a handoff; another refund's key. An
  intruder is refused for being one, before anything about the proposal is told;
- nothing that must never happen is in the database: a unit paid twice or before it came back, a refund without the
  customer's confirmation and a staff approval of that exact proposal in time, amounts or payments that disagree, an
  agent change after a handoff, a final status that changed, or a refund the backend did not answer with a receipt.
  A rightful retry of a refund gets the same receipt.

A last test acts at moments around a proposal's expiry, the moment itself and the minute before always included.

A failing sequence is shrunk to a short one and printed, and Hypothesis replays it first on the next run. These
explore orders of actions nobody wrote down; the races need real concurrency and stay in their own tests
(tests/acceptance/test_concurrency.py). HYPOTHESIS_PROFILE=deep runs ten times as many sequences.
"""

import os
import uuid
from datetime import timedelta
from itertools import combinations

import pytest
from hypothesis import HealthCheck, Phase, event, example, given, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)
from sqlalchemy import text

from refund_agent import db as database
from refund_agent.fixtures import seed
from refund_agent.refunds import Actor, Refused, cancel, confirm, decide, execute, hand_off, open_conversation, propose
from tests.acceptance.flows import DEVELOPMENT, POLICY, rows

FINAL = {"refunded", "ineligible", "rejected", "cancelled", "expired", "invalidated"}
OPEN = ("approved", "awaiting_staff_approval", "awaiting_customer_confirmation")
CURRENCY = "BRL"
settings.register_profile(
    "default",
    max_examples=25,
    stateful_step_count=30,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile("deep", parent=settings.get_profile("default"), max_examples=250)
# For the planted-bug script: whether a bug is found, without shrinking it or saving it for the next run.
settings.register_profile(
    "mutants",
    parent=settings.get_profile("default"),
    phases=[Phase.explicit, Phase.generate],
    database=None,
    print_blob=False,
)
PROFILE = settings.get_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

# What must never be in the database, each a query that returns the offending rows. Refunds seeded as history,
# committed before the scenario's clock, are left out: they were not made through the services.
NEVER = {
    "a unit refunded twice": "SELECT order_unit_id FROM ledger_lines GROUP BY 1 HAVING count(*) > 1",
    "a unit refunded for another amount than was paid for it": (
        "SELECT l.order_unit_id FROM ledger_lines l JOIN order_units u ON u.id = l.order_unit_id "
        "WHERE l.amount_minor <> u.paid_minor"
    ),
    "a unit refunded before it was received back": (
        "SELECT l.order_unit_id FROM ledger_lines l JOIN order_units u ON u.id = l.order_unit_id "
        "JOIN refund_operations o ON o.id = l.operation_id WHERE o.committed_at >= :start "
        "AND (u.received_back_at IS NULL OR u.received_back_at > o.committed_at)"
    ),
    "a refund without the customer's confirmation and a staff approval of that exact proposal, in time": (
        "SELECT o.receipt_number FROM refund_operations o JOIN proposals p ON p.id = o.proposal_id "
        "LEFT JOIN customer_confirmations c ON c.proposal_id = p.id AND c.decision = 'confirmed' "
        "AND c.customer_id = p.customer_id AND c.content_hash = p.content_hash AND c.decided_at <= o.committed_at "
        "LEFT JOIN staff_decisions d ON d.id = o.approval_id AND d.proposal_id = p.id AND d.decision = 'approved' "
        "AND d.content_hash = p.content_hash AND d.decided_at <= o.committed_at "
        "LEFT JOIN users s ON s.id = d.staff_id AND s.role = 'staff' WHERE o.committed_at >= :start "
        "AND (c.id IS NULL OR d.id IS NULL OR s.id IS NULL OR o.committed_at >= p.expires_at "
        "OR p.status <> 'refunded')"
    ),
    "two refunds of one proposal": "SELECT proposal_id FROM refund_operations GROUP BY 1 HAVING count(*) > 1",
    "two refunds with one approval": (
        "SELECT approval_id FROM refund_operations WHERE approval_id IS NOT NULL GROUP BY 1 HAVING count(*) > 1"
    ),
    "a refund whose amount, currency, payment or receipt disagrees with its proposal and lines": (
        "SELECT o.receipt_number FROM refund_operations o JOIN proposals p ON p.id = o.proposal_id "
        "JOIN payments pay ON pay.id = o.payment_id WHERE o.committed_at >= :start AND ("
        "o.amount_minor <> p.amount_minor OR o.currency <> :currency OR p.currency <> :currency "
        "OR o.payment_id <> p.payment_id OR pay.order_id <> p.order_id "
        "OR o.amount_minor <> (SELECT sum(l.amount_minor) FROM ledger_lines l WHERE l.operation_id = o.id) "
        "OR EXISTS (SELECT 1 FROM ledger_lines l WHERE l.operation_id = o.id "
        "AND (l.currency <> o.currency OR l.payment_id <> o.payment_id)) "
        "OR (o.receipt->>'amount_minor')::bigint <> o.amount_minor "
        "OR o.receipt->>'receipt_number' <> o.receipt_number OR o.receipt->>'proposal_id' <> o.proposal_id)"
    ),
    "an agent's proposal or refund after its conversation was handed off": (
        "SELECT later.event || ' in ' || later.conversation_id FROM audit_events handoff JOIN audit_events later "
        "ON later.conversation_id = handoff.conversation_id AND later.id > handoff.id "
        "WHERE handoff.event = 'hand_off' AND handoff.outcome = 'committed' AND later.actor_type = 'agent' "
        "AND later.event IN ('propose', 'execute') AND later.outcome = 'committed'"
    ),
    "a proposal on another customer's order or in another customer's conversation": (
        "SELECT p.id FROM proposals p JOIN orders o ON o.id = p.order_id "
        "JOIN conversations c ON c.id = p.conversation_id "
        "WHERE o.customer_id <> p.customer_id OR c.customer_id <> p.customer_id"
    ),
}
NEVER_SQL = " UNION ALL ".join(
    f"SELECT CAST(:rule{i} AS text), CAST(found.value AS text) FROM ({query}) AS found(value)"
    for i, query in enumerate(NEVER.values())
)


class Shop(RuleBasedStateMachine):
    """One scenario's fixture on a fresh database, and the actions anyone could try on it."""

    template: str
    scenario_id: str
    refunds: list[tuple[int, int]]  # each sequence's refunds, at the start and during its steps, for the run's summary

    def __init__(self) -> None:
        super().__init__()
        self.scenario = DEVELOPMENT[self.scenario_id]
        self.name = f"refund_prop_{uuid.uuid4().hex[:12]}"
        database.create_database(self.name, template=self.template)
        self.owner, self.app = database.engine("owner", self.name), database.engine("app", self.name)
        try:
            seed(self.owner, self.scenario, POLICY)
        except BaseException:
            self.drop()  # Hypothesis calls teardown only for a machine it got
            raise
        fixture = self.scenario.fixture
        self.customers = [c.id for c in fixture.customers]
        self.staff = fixture.staff[0].id
        self.orders = {o.id: [u.id for u in o.units] for o in fixture.orders}
        self.owners = {o.id: o.customer for o in fixture.orders}
        # The scenario's own return records, not the policy: what an honest start would propose.
        self.returned = {
            o.id: [u.id for u in o.units if u.received_back_at and u.received_back_at <= self.scenario.now]
            for o in fixture.orders
        }
        self.now = self.scenario.now
        self.conversations: dict[str, str] = {}  # conversation -> its customer
        self.proposals: dict[str, str] = {}  # proposal -> the conversation it was made in
        self.receipts: dict[str, str] = {}  # proposal -> receipt number, as execute answered
        self.paid_with: dict[str, str] = {}  # execute key -> the proposal whose refund it committed
        self.handed_off: set[str] = set()
        self.final: dict[str, str] = {}  # proposal -> the final status it reached
        self.at_start = 0
        self.turn = 0  # which probe, and which target, comes next

    def teardown(self) -> None:
        try:
            self.refunds.append((self.at_start, len(self.receipts) - self.at_start))
        finally:
            self.drop()

    def drop(self) -> None:
        self.owner.dispose()
        self.app.dispose()
        database.drop_database(self.name)

    def tick(self) -> None:
        self.now += timedelta(minutes=1)

    def statuses(self) -> dict[str, str]:
        return dict(rows(self.owner, "SELECT id, status FROM proposals"))

    def proposal(self, data, *statuses: str) -> str:
        """Mostly a proposal in a status where the action makes sense, the rest of the time any proposal."""
        now = self.statuses()
        fitting = [p for status in statuses for p in self.proposals if now[p] == status]
        return data.draw(st.sampled_from([*fitting, *fitting, *self.proposals]))

    def until_expiry_of(self, proposal: str, early: int) -> None:
        """The next action, a minute later, comes exactly when the proposal expires (early 0) or a minute before
        (early 1): the edge of "strictly before it expires". Time never goes back."""
        with self.owner.connect() as conn:
            expires = conn.execute(
                text("SELECT expires_at FROM proposals WHERE id = :id"), {"id": proposal}
            ).scalar_one()
        self.now = max(self.now, expires - timedelta(minutes=1 + early))

    def owner_of(self, proposal: str) -> str:
        return self.conversations[self.proposals[proposal]]

    def others(self, customer: str) -> list[str]:
        return [c for c in self.customers if c != customer]

    def units(self, data, order: str, units: list[str] | None = None) -> list[str]:
        """One, two or three of the order's units, or of `units`."""
        units = units or self.orders[order]
        return data.draw(
            st.sampled_from([list(c) for n in range(1, min(3, len(units)) + 1) for c in combinations(units, n)])
        )

    # The start

    @initialize(data=st.data())
    def the_shop_is_somewhere_along_the_way(self, data):
        """The actions below then often start next to an approved or a paid proposal, or two proposals for the same
        unit, whichever actions Hypothesis switches on for the sequence."""
        for customer in self.customers:
            own = [o for o, c in self.owners.items() if c == customer]
            for _ in range(2):
                conversation = self.open(customer)
                # Approved and paid twice as often as the rest: money is what the invariants are mostly about.
                stage = data.draw(
                    st.sampled_from(["approved", "paid", "approved", "paid", "confirmed", "proposed", "empty"])
                )
                if stage == "empty" or not own:
                    continue
                order = data.draw(st.sampled_from(own))
                units = self.units(data, order, self.returned[order])
                proposal = self.propose_as(customer, conversation, order, units, f"start-{conversation}")
                if proposal is None or stage == "proposed":
                    continue
                self.attempt(confirm, Actor("customer", customer), proposal, "confirmed")
                if stage in ("approved", "paid"):
                    self.attempt(decide, Actor("staff", self.staff), proposal, "approved")
                if stage == "paid":
                    self.pay(proposal, f"start-{conversation}")
        self.at_start = len(self.receipts)
        event(f"start: {', '.join(sorted(self.statuses().values())) or 'no proposal'}")

    # Rightful actions: refusals are expected (out of date, wrong status, a reused key); any other exception fails.
    # Hypothesis orders the rules by name and picks the first more often: agent_pays_late first, so approvals still
    # wait for it, and agent_pays_now second, so sequences reach the money.

    @rule(data=st.data())
    def customer_opens_another_conversation(self, data):
        self.open(data.draw(st.sampled_from(self.customers)))

    def open(self, customer: str) -> str:
        self.tick()
        conversation = open_conversation(self.app, Actor("customer", customer), self.now)
        self.conversations[conversation] = customer
        return conversation

    @rule(data=st.data())
    def agent_proposes(self, data):
        conversation = data.draw(st.sampled_from(list(self.conversations)))
        customer = self.conversations[conversation]
        own = [o for o, c in self.owners.items() if c == customer]
        if not own:
            return
        order = data.draw(st.sampled_from(own))
        key = data.draw(st.sampled_from(["propose-a", "propose-b", f"propose-{len(self.proposals)}"]))
        self.propose_as(customer, conversation, order, self.units(data, order), key)

    def propose_as(self, agent_of: str, conversation: str, order: str, units: list[str], key: str) -> str | None:
        self.tick()
        try:
            result = propose(self.app, Actor("agent", agent_of), conversation, order, units, key, self.now, POLICY)
        except Refused as refused:
            event(f"propose refused: {refused.check}")
            return None
        event(f"propose stored: {result.status}")
        self.proposals.setdefault(result.id, conversation)
        return result.id

    @precondition(lambda self: self.proposals)
    @rule(data=st.data())
    def customer_answers_the_card(self, data):
        proposal = self.proposal(data, "awaiting_customer_confirmation")
        decision = data.draw(st.sampled_from(["confirmed", "confirmed", "declined"]))
        self.attempt(confirm, Actor("customer", self.owner_of(proposal)), proposal, decision)

    @precondition(lambda self: self.proposals)
    @rule(data=st.data())
    def staff_decides(self, data):
        proposal = self.proposal(data, "awaiting_staff_approval")
        decision = data.draw(st.sampled_from(["approved", "approved", "rejected"]))
        self.attempt(decide, Actor("staff", self.staff), proposal, decision)

    @precondition(lambda self: self.proposals)
    @rule(data=st.data())
    def agent_pays_now(self, data):
        proposal = self.proposal(data, "approved", "refunded")
        self.pay(proposal, data.draw(st.sampled_from(self.keys(proposal))))

    @precondition(lambda self: self.proposals)
    @rule(data=st.data())
    def agent_pays_late(self, data):
        """Exactly when an approval expires, or a minute before: an approval left for three days. Without an approval
        still ahead of its expiry, a refund's retry at its expiry, which must get the receipt still."""
        found = rows(self.owner, "SELECT id, status, expires_at FROM proposals")
        ahead = {
            p for p, status, expires in found if status == "approved" and expires - self.now >= timedelta(minutes=2)
        }
        paid = {p for p, status, _ in found if status == "refunded"}
        choices = [p for p in self.proposals if p in (ahead or paid)]
        if not choices:
            return
        proposal, early = data.draw(st.sampled_from(choices)), data.draw(st.sampled_from([0, 1]))
        self.until_expiry_of(proposal, early)
        event(f"late pay of an {'approval' if ahead else 'refund'}, {early} minutes before its expiry")
        self.pay(proposal, data.draw(st.sampled_from(self.keys(proposal))))

    @staticmethod
    def keys(proposal: str) -> list[str]:
        """The proposal's own key, a second one (a retry with a new key), or one shared by all (a conflict)."""
        return [f"execute-{proposal}", f"execute-{proposal}-again", "execute-shared"]

    def pay(self, proposal: str, key: str) -> None:
        home = self.proposals[proposal]
        self.tick()
        agent = Actor("agent", self.owner_of(proposal))
        try:
            receipt = execute(self.app, agent, proposal, key, self.now, POLICY, conversation_id=home)
        except Refused as refused:
            event(f"execute refused: {refused.check}")
            # A retry of a refund gets its receipt, after a handoff or expiry too; only a key already used for another
            # request is refused.
            assert proposal not in self.receipts or refused.check == "request_key_consistent", (
                f"a retry of a refund was refused: {refused.check}"
            )
            return
        event("execute returned the same receipt" if proposal in self.receipts else "execute committed a refund")
        assert receipt["proposal_id"] == proposal, "the receipt is another proposal's"
        if proposal not in self.receipts:
            self.paid_with[key] = proposal
        # A retry, with this key or another, returns the receipt already given for this proposal.
        assert self.receipts.setdefault(proposal, receipt["receipt_number"]) == receipt["receipt_number"]

    @precondition(lambda self: self.proposals)
    @rule(data=st.data())
    def customer_cancels(self, data):
        proposal = self.proposal(data, "awaiting_customer_confirmation", "awaiting_staff_approval", "approved")
        self.attempt(cancel, Actor("customer", self.owner_of(proposal)), proposal)

    @precondition(lambda self: len(self.handed_off) < len(self.conversations))
    @rule(data=st.data())
    def someone_asks_for_a_person(self, data):
        # Mostly a conversation still with the agent, so that a handoff does not end every sequence's story early.
        live = [c for c in self.conversations if c not in self.handed_off]
        conversation = data.draw(st.sampled_from([*live, *self.conversations]))
        by_agent = data.draw(st.booleans())
        actor = Actor("agent" if by_agent else "customer", self.conversations[conversation])
        self.tick()
        try:
            hand_off(
                self.app, actor, conversation, "asked for a person", self.now, origin="agent" if by_agent else None
            )
        except Refused as refused:
            event(f"hand_off refused: {refused.check}")
            return
        event("hand_off committed")
        self.handed_off.add(conversation)

    @rule(hours=st.sampled_from([1, 24, 80]))
    def time_passes(self, hours):
        self.now += timedelta(hours=hours)

    @rule(data=st.data())
    def time_reaches_an_open_proposals_expiry(self, data):
        now = self.statuses()
        open_ = [p for p in self.proposals if now[p] in OPEN]
        if open_:
            self.until_expiry_of(data.draw(st.sampled_from(open_)), early=data.draw(st.sampled_from([0, 1])))

    def attempt(self, service, actor: Actor, proposal: str, *decision: str) -> None:
        """confirm, decide or cancel, a minute after the last action; a refusal is recorded and is no failure."""
        self.tick()
        try:
            service(self.app, actor, proposal, *decision, self.now, POLICY)
        except Refused as refused:
            event(f"{service.__name__} refused: {refused.check}")
            return
        event(f"{service.__name__} committed")

    # Probes: after every step, one action that must be refused in the state just reached, each kind in turn and
    # each target in turn. Left to Hypothesis's draws, some kinds came once or twice a run, and a planted bug they
    # alone reveal was missed by chance. A refused action changes nothing but the audit log, so a probe does not
    # steer the sequence, and it keeps the time of the step before.

    def pick(self, items: list):
        return items[(self.turn // len(PROBES)) % len(items)]

    def fitting(self, *statuses: str) -> list[str]:
        """The proposals in these statuses, or every proposal if none is."""
        now = self.statuses()
        return [p for p in self.proposals if now[p] in statuses] or list(self.proposals)

    def must_refuse(self, name: str, expected: set[str], action) -> bool:
        try:
            action()
        except Refused as refused:
            event(f"probe {name} refused: {refused.check}")
            assert refused.check in expected, f"{name} was refused for {refused.check}, not {sorted(expected)}"
            return True
        raise AssertionError(f"{name} was allowed")

    def pay_from_elsewhere(self) -> bool:
        """Another conversation of the same customer, or another customer's agent: the handoff bypass of the review."""
        if not self.proposals:
            return False
        proposal = self.pick(self.fitting("approved", "refunded"))
        rightful = (self.owner_of(proposal), self.proposals[proposal])
        agent_of, origin = self.pick([(c, o) for c in self.customers for o in self.conversations if (c, o) != rightful])
        agent, key = Actor("agent", agent_of), f"execute-{proposal}"
        return self.must_refuse(
            "a payment from elsewhere",
            {"actor_owns", "same_conversation"},
            lambda: execute(self.app, agent, proposal, key, self.now, POLICY, conversation_id=origin),
        )

    def decide_as_staff(self) -> bool:
        if not self.proposals:
            return False
        proposal, who = self.pick(self.fitting("awaiting_staff_approval")), Actor("staff", self.pick(self.customers))
        return self.must_refuse(
            "a customer's staff decision",
            {"staff_role"},
            lambda: decide(self.app, who, proposal, "approved", self.now, POLICY),
        )

    def propose_for_someone_else(self) -> bool:
        if len(self.customers) < 2:
            return False
        conversation = self.pick(list(self.conversations))
        customer = self.conversations[conversation]
        foreign = [o for o, c in self.owners.items() if c != customer]
        if self.turn % 2 or not foreign:  # another customer's agent in this conversation
            agent_of, order = self.pick(self.others(customer)), self.pick(list(self.orders))
        else:  # this conversation's agent, on another customer's order
            agent_of, order = customer, self.pick(foreign)
        agent, units, key = Actor("agent", agent_of), self.orders[order][:1], f"intruder-{self.turn}"
        return self.must_refuse(
            "a proposal for someone else",
            {"actor_owns"},
            lambda: propose(self.app, agent, conversation, order, units, key, self.now, POLICY),
        )

    def hand_off_someone_elses(self) -> bool:
        if len(self.customers) < 2:
            return False
        conversation = self.pick(list(self.conversations))
        who = Actor("customer", self.pick(self.others(self.conversations[conversation])))
        return self.must_refuse(
            "a handoff of someone else's conversation",
            {"actor_owns"},
            lambda: hand_off(self.app, who, conversation, "asked for a person", self.now),
        )

    def press_someone_elses_card(self) -> bool:
        if len(self.customers) < 2 or not self.proposals:
            return False
        proposal = self.pick(self.fitting("awaiting_customer_confirmation"))
        who = Actor("customer", self.pick(self.others(self.owner_of(proposal))))
        decision = self.pick(["confirmed", "declined"])
        return self.must_refuse(
            "someone else's confirmation",
            {"actor_owns"},
            lambda: confirm(self.app, who, proposal, decision, self.now, POLICY),
        )

    def cancel_someone_elses(self) -> bool:
        if len(self.customers) < 2 or not self.proposals:
            return False
        proposal = self.pick(self.fitting(*OPEN))
        who = Actor("customer", self.pick(self.others(self.owner_of(proposal))))
        return self.must_refuse(
            "someone else's cancellation", {"actor_owns"}, lambda: cancel(self.app, who, proposal, self.now, POLICY)
        )

    def cancel_a_closed_proposal(self) -> bool:
        """The rightful customer, on a proposal already final: a final status never changes."""
        now = self.statuses()
        closed = [p for p in self.proposals if now[p] in FINAL]
        if not closed:
            return False
        proposal = self.pick(closed)
        who = Actor("customer", self.owner_of(proposal))
        return self.must_refuse(
            "a cancellation of a closed proposal",
            {"invalid_transition"},
            lambda: cancel(self.app, who, proposal, self.now, POLICY),
        )

    def propose_after_a_handoff(self) -> bool:
        """The rightful agent, on its customer's own order, in a conversation a person has taken over."""
        own = {c: [o for o, owner in self.owners.items() if owner == c] for c in self.customers}
        handed = [c for c in self.conversations if c in self.handed_off and own[self.conversations[c]]]
        if not handed:
            return False
        conversation = self.pick(handed)
        customer = self.conversations[conversation]
        order = self.pick(own[customer])
        agent, units, key = Actor("agent", customer), self.orders[order][:1], f"after-handoff-{self.turn}"
        return self.must_refuse(
            "a proposal after a handoff",
            {"agent_in_control"},
            lambda: propose(self.app, agent, conversation, order, units, key, self.now, POLICY),
        )

    def pay_with_another_refunds_key(self) -> bool:
        """A key that committed another proposal's refund is a conflict, whatever this proposal's state."""
        pairs = [(k, p) for k, paid in self.paid_with.items() for p in self.proposals if p != paid]
        if not pairs:
            return False
        key, proposal = self.pick(pairs)
        agent, home = Actor("agent", self.owner_of(proposal)), self.proposals[proposal]
        return self.must_refuse(
            "another refund's key",
            {"request_key_consistent"},
            lambda: execute(self.app, agent, proposal, key, self.now, POLICY, conversation_id=home),
        )

    # Invariants: after every step

    @invariant()
    def what_must_be_refused_is_refused(self):
        """One probe, the next kind in turn that applies to the state reached."""
        for i in range(len(PROBES)):
            if PROBES[(self.turn + i) % len(PROBES)](self):
                break
        self.turn += 1

    @invariant()
    def nothing_that_must_never_happen_is_in_the_database(self):
        names = {f"rule{i}": name for i, name in enumerate(NEVER)}
        with self.owner.connect() as conn:
            found = conn.execute(text(NEVER_SQL), {**names, "start": self.scenario.now, "currency": CURRENCY}).all()
        assert [tuple(row) for row in found] == []

    @invariant()
    def a_final_status_never_changes(self):
        for proposal, status in rows(self.owner, "SELECT id, status FROM proposals"):
            if proposal in self.final:
                assert status == self.final[proposal], f"{proposal} left {self.final[proposal]} for {status}"
            elif status in FINAL:
                self.final[proposal] = status

    @invariant()
    def the_database_holds_exactly_the_refunds_answered_with_a_receipt(self):
        with self.owner.connect() as conn:
            stored = conn.execute(
                text("SELECT receipt_number FROM refund_operations WHERE committed_at >= :start"),
                {"start": self.scenario.now},
            ).scalars()
            assert set(stored) == set(self.receipts.values())


PROBES = [
    Shop.pay_from_elsewhere,
    Shop.press_someone_elses_card,
    Shop.decide_as_staff,
    Shop.propose_for_someone_else,
    Shop.cancel_someone_elses,
    Shop.hand_off_someone_elses,
    Shop.cancel_a_closed_proposal,
    Shop.propose_after_a_handoff,
    Shop.pay_with_another_refunds_key,
]


@pytest.mark.parametrize(
    "scenario_id",
    [
        "D02",  # one customer, two units that can be refunded and one not yet returned
        "D07",  # two customers, each also acting as an intruder on the other's conversations and proposals
    ],
)
def test_no_sequence_of_actions_breaks_the_invariants(template_db, scenario_id):
    machine = type(f"Shop{scenario_id}", (Shop,), {"template": template_db, "scenario_id": scenario_id, "refunds": []})
    run_state_machine_as_test(machine, settings=PROFILE)
    # Without a refund the invariants about money would hold trivially: most sequences start with one or reach one.
    some = sum(1 for start, during in machine.refunds if start or during)
    during = sum(1 for _, n in machine.refunds if n)
    print(f"{scenario_id}: {some} of {len(machine.refunds)} sequences had a refund, {during} paid during the steps")
    assert some > 0, f"none of {len(machine.refunds)} sequences had a refund"


EDGE = DEVELOPMENT["D02"]


@settings(PROFILE, max_examples=12)
@example(action="confirm", minutes=0)
@example(action="confirm", minutes=-1)
@example(action="decide", minutes=0)
@example(action="decide", minutes=-1)
@example(action="execute", minutes=0)
@example(action="execute", minutes=-1)
@given(action=st.sampled_from(["confirm", "decide", "execute"]), minutes=st.integers(-180, 180))
def test_a_proposal_can_be_acted_on_only_strictly_before_it_expires(template_db, action, minutes):
    """Confirm, decide or pay `minutes` after the proposal's expiry: allowed only before it, refused at it and after.
    The minute before and the moment itself always run, whatever Hypothesis draws."""
    name = f"refund_edge_{uuid.uuid4().hex[:12]}"
    database.create_database(name, template=template_db)
    owner, app = database.engine("owner", name), database.engine("app", name)
    try:
        seed(owner, EDGE, POLICY)
        order = EDGE.fixture.orders[0]
        unit = next(u.id for u in order.units if u.received_back_at)
        customer, agent, staff = (
            Actor(kind, who)
            for kind, who in [
                ("customer", order.customer),
                ("agent", order.customer),
                ("staff", EDGE.fixture.staff[0].id),
            ]
        )
        start = EDGE.now
        conversation = open_conversation(app, customer, start)
        proposal = propose(app, agent, conversation, order.id, [unit], "k", start, POLICY).id
        expires = rows(owner, f"SELECT expires_at FROM proposals WHERE id = '{proposal}'")[0][0]
        at = expires + timedelta(minutes=minutes)
        if action in ("decide", "execute"):
            confirm(app, customer, proposal, "confirmed", start, POLICY)
        if action == "execute":
            decide(app, staff, proposal, "approved", start, POLICY)
        steps = {
            "confirm": lambda: confirm(app, customer, proposal, "confirmed", at, POLICY),
            "decide": lambda: decide(app, staff, proposal, "approved", at, POLICY),
            "execute": lambda: execute(app, agent, proposal, "e", at, POLICY, conversation_id=conversation),
        }
        try:
            steps[action]()
            allowed = True
        except Refused as refused:
            assert refused.check == "proposal_current", refused.check
            allowed = False
        assert allowed == (minutes < 0), f"{action} {minutes} minutes after the expiry: allowed={allowed}"
    finally:
        owner.dispose()
        app.dispose()
        database.drop_database(name)
