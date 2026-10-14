"""Serve the HTTP layer on a local demo database: `uv run python -m refund_agent.api` (Ctrl+C stops it).

Needs the local database (`docker compose up -d`). Recreates the database refund_demo_api, loads scenario D01 and
gives its fictional users the demo password below. The agent behind the chat door is the scripted model of mock mode
(refund_agent/evaluation/mock_scripts.py), in configuration A, so no API key is needed: it plays a careful agent for
Ana's mug, whatever is typed. The business clock starts at the scenario's time and moves with real time. Every door
can be tried at http://localhost:8000/docs; changes need the csrf_token of the sign-in answer in X-CSRF-Token.
"""

from __future__ import annotations

from datetime import UTC, datetime

import uvicorn
from langgraph.checkpoint.postgres import PostgresSaver

from refund_agent import db as database
from refund_agent.agent.graph import Agent
from refund_agent.agent.model import ScriptedModel
from refund_agent.api.app import create_app
from refund_agent.api.auth import set_password
from refund_agent.evaluation.mock_scripts import MOCK
from refund_agent.fixtures import seed
from refund_agent.policy import load_policy
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

    pool = database.checkpoint_pool("app", NAME)
    agent = Agent(app_engine, policy, ScriptedModel(MOCK[SCENARIO].agent), PostgresSaver(pool), clock)
    emails = {p.id: p.email for p in (*scenario.fixture.customers, *scenario.fixture.staff)}
    print(f"Database {NAME}: scenario {scenario.id}, business clock from {scenario.now}")
    print(
        f"Customer {emails[scenario.customer.id]}, staff {emails[scenario.fixture.staff[0].id]}; password in {__file__}"
    )
    print("Agent: the scripted model of mock mode, configuration A")
    print("API documentation: http://localhost:8000/docs")
    try:
        # Plain HTTP on this machine only, so the cookie cannot be marked Secure here; behind HTTPS it must be.
        uvicorn.run(
            create_app(app_engine, policy, clock, secure_cookies=False, agent=agent), host="127.0.0.1", port=8000
        )
    finally:
        pool.close()


if __name__ == "__main__":
    main()
