"""Serve the HTTP layer on a local demo database: `uv run python -m refund_agent.api` (Ctrl+C stops it).

Needs the local database (`docker compose up -d`). Recreates the database refund_demo_api, loads scenario D01, gives
its fictional users the demo password below, and opens a conversation with a proposal for Ana's mug, made through
the same service the agent will call in phase 3 (there is no HTTP door for proposing). The business clock starts at
the scenario's time and moves with real time, so the scenario's deadlines hold. Every door can be tried in the API
documentation at http://localhost:8000/docs; changes need the csrf_token of the sign-in answer in X-CSRF-Token.
"""

from __future__ import annotations

from datetime import UTC, datetime

import uvicorn

from refund_agent import db as database
from refund_agent.api.app import create_app
from refund_agent.api.auth import set_password
from refund_agent.fixtures import seed
from refund_agent.policy import load_policy
from refund_agent.refunds import Actor, open_conversation, propose
from refund_agent.scenarios import load_split

NAME = "refund_demo_api"
SCENARIO = "D01"
# For the fictional users of the local demo only.
DEMO_PASSWORD = "refund-demo-local"


def main() -> None:
    policy = load_policy()
    scenario = next(s for s in load_split("development") if s.id == SCENARIO)
    database.create_database(NAME)
    database.migrate(NAME)
    owner = database.engine("owner", NAME)
    seed(owner, scenario, policy)
    for person in (*scenario.fixture.customers, *scenario.fixture.staff):
        set_password(owner, person.id, DEMO_PASSWORD)
    owner.dispose()

    app_engine = database.engine("app", NAME)
    started = datetime.now(UTC)

    def clock() -> datetime:
        return scenario.now + (datetime.now(UTC) - started)

    customer = scenario.customer.id
    conversation = open_conversation(app_engine, Actor("customer", customer), clock())
    units = list(scenario.customer.confirms.units)
    order = scenario.fixture.order_of_unit()[units[0]].id
    proposal = propose(app_engine, Actor("agent", customer), conversation, order, units, "demo-1", clock(), policy)

    emails = {p.id: p.email for p in (*scenario.fixture.customers, *scenario.fixture.staff)}
    print(f"Database {NAME}: scenario {scenario.id}, business clock from {scenario.now}")
    print(f"Customer {emails[customer]}, staff {emails[scenario.fixture.staff[0].id]}; password in {__file__}")
    print(f"Conversation {conversation}, proposal {proposal.id} ({proposal.status}, {proposal.amount_minor} centavos)")
    print("API documentation: http://localhost:8000/docs")
    # Plain HTTP on this machine only, so the cookie cannot be marked Secure here; behind HTTPS it must be.
    uvicorn.run(create_app(app_engine, policy, clock, secure_cookies=False), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
