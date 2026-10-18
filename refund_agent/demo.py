"""See one refund go through the backend without any LLM: `uv run python -m refund_agent.demo`.

Needs the local database (`docker compose up -d`). Recreates the database `refund_demo`, loads scenario D01 and runs
the flow step by step, printing what the backend decides and what it stores. The database is left in place, so it
can be inspected afterwards.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import text

from refund_agent import db as database
from refund_agent.fixtures import seed
from refund_agent.policy import load_policy
from refund_agent.refunds import Actor, Refused, confirm, decide, execute, open_conversation, propose
from refund_agent.scenarios import format_brl, load_split

NAME = "refund_demo"


def step(title: str) -> None:
    print(f"\n== {title}")


def main() -> None:
    policy = load_policy()
    scenario = next(s for s in load_split("development") if s.id == "D01")
    database.create_database(NAME)
    database.migrate(NAME)
    seed(database.engine("owner", NAME), scenario, policy)
    app = database.engine("app", NAME)
    customer, agent, staff = Actor("customer", "d01-ana"), Actor("agent", "d01-ana"), Actor("staff", "d01-rui")

    def at(minutes: int):
        return scenario.now + timedelta(minutes=minutes)

    print(f"Database {NAME}: scenario {scenario.id} ({scenario.title}), policy {policy.version}, clock {scenario.now}")

    step("1. The customer opens a conversation")
    conversation = open_conversation(app, customer, at(0))
    print(f"   conversation {conversation}")

    step("2. The agent asks the backend for a proposal for the blue mug")
    proposal = propose(app, agent, conversation, "d01-o1", ["d01-o1-u1"], "propose-1", at(1), policy)
    print(
        f"   proposal {proposal.id}: {proposal.status}, amount {format_brl(proposal.amount_minor)} "
        "(computed by the backend; shipping not included)"
    )

    step("3. The agent tries to execute before anyone agreed")
    try:
        execute(app, agent, proposal.id, "execute-early", at(2), policy, conversation_id=conversation)
    except Refused as refused:
        print(f"   refused by check '{refused.check}'; nothing written")

    step("4. The customer confirms on the proposal card")
    print(f"   status: {confirm(app, customer, proposal.id, 'confirmed', at(3), policy)}")

    step("5. The staff member approves")
    print(f"   status: {decide(app, staff, proposal.id, 'approved', at(4), policy)}")

    step("6. The agent executes the refund")
    receipt = execute(app, agent, proposal.id, "execute-1", at(5), policy, conversation_id=conversation)
    print(
        f"   receipt {receipt['receipt_number']}: {format_brl(receipt['amount_minor'])} "
        f"to payment {receipt['payment_id']}"
    )

    step("7. The HTTP answer is lost; the agent retries with the same key, then with a new key")
    same_key = execute(app, agent, proposal.id, "execute-1", at(6), policy, conversation_id=conversation)
    new_key = execute(app, agent, proposal.id, "execute-2", at(7), policy, conversation_id=conversation)
    print(f"   same receipt both times: {same_key == receipt and new_key == receipt}")

    step("8. What the database holds")
    with app.connect() as conn:
        operations, total = conn.execute(
            text("SELECT count(*), CAST(sum(amount_minor) AS bigint) FROM refund_operations")
        ).one()
        lines = conn.execute(text("SELECT count(*) FROM ledger_lines")).scalar_one()
        status = conn.execute(text("SELECT status FROM proposals")).scalar_one()
        print(f"   proposal: {status}; refund operations: {operations} ({format_brl(total)}); ledger lines: {lines}")
        print("   audit log:")
        for event, actor, outcome, reason in conn.execute(
            text("SELECT event, actor_type, outcome, reason FROM audit_events ORDER BY id")
        ):
            print(f"     {event:<18} {actor:<9} {outcome:<10} {reason or ''}")
    app.dispose()


if __name__ == "__main__":
    main()
