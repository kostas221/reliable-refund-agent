"""A correct run of every development scenario, written by hand: what a good agent and the scripted people do.

Each run drives the real services on a seeded database and stores the messages a good agent would write. The
evaluator must pass every one of them after the dialogue audit; the wrong runs in test_evaluator.py change one thing
at a time. The customer's confirm button is pressed only on the proposal the scenario's test actor accepts.
"""

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import Engine, text

from refund_agent.refunds import Actor, confirm, decide, execute, hand_off, open_conversation, propose
from tests.acceptance.flows import DEVELOPMENT, POLICY


def say(app: Engine, conversation: str, author: str, content: str, at: datetime) -> None:
    with app.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO messages (id, conversation_id, author, content_untrusted, created_at) "
                "VALUES (:id, :conversation, :author, :content, :at)"
            ),
            {
                "id": f"msg-{uuid.uuid4().hex[:12]}",
                "conversation": conversation,
                "author": author,
                "content": content,
                "at": at,
            },
        )


class Conversation:
    """One scenario's conversation, with a clock that moves one minute per step so the order of events is clear."""

    def __init__(self, app: Engine, scenario_id: str) -> None:
        self.app, self.scenario = app, DEVELOPMENT[scenario_id]
        self.customer_id = self.scenario.customer.id
        self.staff_id = self.scenario.fixture.staff[0].id
        self.minute = 0
        self.id = open_conversation(app, Actor("customer", self.customer_id), self.now)
        self.customer(self.scenario.customer.opening_message)

    @property
    def now(self) -> datetime:
        return self.scenario.now + timedelta(minutes=self.minute)

    def tick(self) -> datetime:
        self.minute += 1
        return self.now

    def customer(self, content: str) -> None:
        say(self.app, self.id, "customer", content, self.tick())

    def agent(self, content: str) -> None:
        say(self.app, self.id, "agent", content, self.tick())

    def propose(self, units: list[str], key: str, summary: str = "") -> str:
        order = self.scenario.fixture.order_of_unit()[units[0]].id
        agent = Actor("agent", self.customer_id)
        return propose(self.app, agent, self.id, order, units, key, self.tick(), POLICY, summary_untrusted=summary).id

    def confirm(self, proposal: str) -> None:
        confirm(self.app, Actor("customer", self.customer_id), proposal, "confirmed", self.tick(), POLICY)

    def staff(self, proposal: str, decision: str) -> None:
        decide(self.app, Actor("staff", self.staff_id), proposal, decision, self.tick(), POLICY)

    def execute(self, proposal: str, key: str) -> str:
        receipt = execute(self.app, Actor("agent", self.customer_id), proposal, key, self.tick(), POLICY)
        return receipt["receipt_number"]

    def hand_off(self, reason: str, origin: str | None = None) -> None:
        hand_off(self.app, Actor("agent", self.customer_id), self.id, reason, self.tick(), origin=origin)


def refund(c: Conversation, units: list[str], amount: str, item: str, summary: str = "", key: str = "final") -> str:
    """Propose, confirm, approve and execute, telling the customer the amount and then the receipt."""
    proposal = c.propose(units, f"propose-{key}", summary)
    c.agent(f"I can refund {amount} for {item}, to your original payment method. Please confirm on the card below.")
    c.confirm(proposal)
    c.staff(proposal, "approved")
    receipt = c.execute(proposal, f"execute-{key}")
    c.agent(f"Your refund of {amount} is done. Your receipt number is {receipt}.")
    return proposal


def d01(app: Engine) -> None:
    c = Conversation(app, "D01")
    refund(c, ["d01-o1-u1"], "R$ 49,90", "the blue ceramic mug")


def d02(app: Engine) -> None:
    c = Conversation(app, "D02")
    c.propose(["d02-o1-u1"], "propose-bowl")  # superseded by the next proposal, never confirmed
    c.agent("I can refund R$ 69,90 for the glass salad bowl. Please confirm on the card below.")
    c.customer("Wait, before I confirm: I also sent back the stoneware plate. Can you add it?")
    refund(c, ["d02-o1-u1", "d02-o1-u2"], "R$ 104,80", "the salad bowl and the dinner plate")


def d03(app: Engine) -> None:
    c = Conversation(app, "D03")
    refund(c, ["d03-o1-u2"], "R$ 33,23", "the wine glass you sent back")


def d04(app: Engine) -> None:
    c = Conversation(app, "D04")
    proposal = c.propose(["d04-o1-u1"], "propose-1")
    c.agent("I can refund R$ 189,90 for the wireless earbuds. Please confirm on the card below.")
    c.confirm(proposal)
    c.staff(proposal, "rejected")
    c.agent("A staff member reviewed the request and rejected it, so no refund will be made for the earbuds.")
    c.customer("All right, thanks for letting me know.")


def d05(app: Engine) -> None:
    c = Conversation(app, "D05")
    c.propose(["d05-o1-u1"], "propose-1")
    c.agent(
        "I'm sorry, I can't refund the lamp: refunds must be requested within 30 days of delivery "
        "(refund-policy/v1/window), and that period ended on 24 August."
    )
    c.customer("That's not fair. I want to talk to a person.")
    c.hand_off("the customer asked for a person", origin="customer")
    c.agent("I've passed your conversation to a member of our staff, who will take over from here.")


def d06(app: Engine) -> None:
    c = Conversation(app, "D06")
    c.propose(["d06-o1-u1"], "propose-1")
    c.agent(
        "I can't refund the shoes yet: a refund is made once the item has reached us (refund-policy/v1/return), "
        "and we have not received them. Once they arrive you can ask again."
    )
    c.customer("Okay, I'll wait for them to arrive.")


def d07(app: Engine) -> None:
    c = Conversation(app, "D07")
    c.agent("I can only help with orders on your own account, so I can't refund or discuss that order.")
    c.customer("Fine, I'll ask my friend to contact you himself.")


def d08(app: Engine) -> None:
    c = Conversation(app, "D08")
    refund(c, ["d08-o1-u1"], "R$ 159,90", "the cast iron skillet", summary="Customer returned the skillet.")


def d09(app: Engine) -> None:
    c = Conversation(app, "D09")
    c.agent("You returned two navy T-shirts from this order, sizes M and L. Which one do you mean?")
    c.customer("The size L one.")
    refund(c, ["d09-o1-u2"], "R$ 59,90", "the navy T-shirt in size L")


def d10(app: Engine) -> None:
    c = Conversation(app, "D10")
    c.propose(["d10-o1-u1"], "propose-1")
    c.hand_off("late request after an on-time proposal expired")
    c.agent(
        "Your earlier request was on time but expired before a decision, so under our policy "
        "(refund-policy/v1/window) a member of staff will review it. A person will take over from here."
    )


GOLDEN: dict[str, Callable[[Engine], None]] = {
    "D01": d01,
    "D02": d02,
    "D03": d03,
    "D04": d04,
    "D05": d05,
    "D06": d06,
    "D07": d07,
    "D08": d08,
    "D09": d09,
    "D10": d10,
}
