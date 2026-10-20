"""Serve the HTTP layer on a local demo database: `uv run python -m refund_agent.api [--scenario D04] [--keep]`.

Needs the local database (`docker compose up -d`); Ctrl+C stops the server. Recreates the database refund_demo_api,
loads one development scenario (D01, Ana's mug, unless another is named) and gives its fictional users the demo
password below. With --keep it serves the database of the previous run as it is, to show that a restart loses nothing
(plan section 13, case 8). The agent behind the chat door is the scripted model of mock mode
(refund_agent/evaluation/mock_scripts.py), in configuration A, so no API key is needed: it plays that scenario's
careful agent, whatever is typed. The business clock starts at the scenario's time, or after the last stored event
with --keep, and moves with real time. Every door can be tried at http://localhost:8000/docs; changes need the
csrf_token of the sign-in answer in X-CSRF-Token.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

import uvicorn
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from refund_agent import db as database
from refund_agent.agent.graph import Agent
from refund_agent.agent.model import ScriptedModel
from refund_agent.api.app import create_app
from refund_agent.api.auth import set_password
from refund_agent.evaluation.mock_scripts import MOCK
from refund_agent.fixtures import seed
from refund_agent.scenarios import load_split, policy_for

NAME = "refund_demo_api"
# For the fictional users of the local demo only.
DEMO_PASSWORD = "refund-demo-local"


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the HTTP layer on a local demo database, in mock mode.")
    parser.add_argument("--scenario", default="D01", choices=sorted(MOCK), help="development scenario to load")
    parser.add_argument("--keep", action="store_true", help="serve the previous run's database instead of a new one")
    args = parser.parse_args()
    scenario = next(s for s in load_split("development") if s.id == args.scenario)
    policy = policy_for([scenario])
    start = kept(scenario.customer.id, scenario.now) if args.keep else None
    if args.keep and start is None:
        sys.exit(f"No demo database of scenario {scenario.id} to keep: run once without --keep.")
    if start is None:
        database.create_database(NAME)
        database.migrate(NAME)
        owner = database.engine("owner", NAME)
        seed(owner, scenario, policy)
        for person in (*scenario.fixture.customers, *scenario.fixture.staff):
            set_password(owner, person.id, DEMO_PASSWORD)
        owner.dispose()

    app_engine = database.engine("app", NAME)
    business_start = start or scenario.now
    started = datetime.now(UTC)

    def clock() -> datetime:
        return business_start + (datetime.now(UTC) - started)

    pool = database.checkpoint_pool("app", NAME)
    agent = Agent(app_engine, policy, ScriptedModel(MOCK[scenario.id].agent), PostgresSaver(pool), clock)
    emails = {p.id: p.email for p in (*scenario.fixture.customers, *scenario.fixture.staff)}
    print(
        f"Database {NAME} ({'kept' if start else 'new'}): scenario {scenario.id}, business clock from {business_start}"
    )
    print(f"Customer {emails[scenario.customer.id]}, staff {emails[scenario.fixture.staff[0].id]}")
    print(f"Every demo user's password is in {__file__}")
    print("Agent: the scripted model of mock mode, configuration A")
    print("API documentation: http://localhost:8000/docs")
    try:
        # Plain HTTP on this machine only, so the cookie cannot be marked Secure here; behind HTTPS it must be.
        uvicorn.run(
            create_app(app_engine, policy, clock, secure_cookies=False, agent=agent, deliver_every_s=5),
            host="127.0.0.1",
            port=8000,
        )
    finally:
        pool.close()


def kept(customer_id: str, at_least: datetime) -> datetime | None:
    """When the previous run's database holds this scenario: the business time of its last stored event (not before
    `at_least`), so the clock goes on from there instead of going back. Sessions count real time and are left out.
    None when there is no such database."""
    owner = database.engine("owner", NAME)
    try:
        with owner.connect() as conn:
            if conn.execute(text("SELECT 1 FROM users WHERE id = :id"), {"id": customer_id}).first() is None:
                return None
            latest = conn.execute(
                text("SELECT greatest((SELECT max(at) FROM audit_events), (SELECT max(created_at) FROM messages))")
            ).scalar()
    except OperationalError:
        return None
    finally:
        owner.dispose()
    database.migrate(NAME)
    return max(latest, at_least) if latest else at_least


if __name__ == "__main__":
    main()
