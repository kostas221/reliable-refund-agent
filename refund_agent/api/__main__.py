"""Serve the HTTP layer on a local demo database.

    uv run python -m refund_agent.api [--scenario D01] [--keep]
    uv run --env-file .env python -m refund_agent.api --live --budget-usd 1 --prices-checked DATE [--scenario D09]

Needs the local database (`docker compose up -d`); Ctrl+C stops the server. Recreates the database refund_demo_api,
loads one development scenario (D01, Ana's mug, unless another is named) and gives its fictional users the demo
password below. With --keep it serves the database of the previous run as it is, to show that a restart loses nothing
(plan section 13, case 8); staff decisions whose delivery to the agent failed three times get new attempts then.

Mock mode is the default: the agent behind the chat door is the scripted model of mock mode
(refund_agent/evaluation/mock_scripts.py), in configuration A, so no API key is needed; it plays that scenario's
careful agent, whatever is typed. With --live it is the evaluated agent (GPT-6.1 Sol, reasoning low, unless named
otherwise) through the OpenAI Responses API, which costs money: the owner starts every such session, with a budget
for the whole server and the date the prices were checked, and every request is written in full to
runs/live-<time>/agent-requests.jsonl (kept out of git). What it may spend and how it pauses: refund_agent/api/live.py.

The business clock starts at the scenario's time, or after the last stored event with --keep, and moves with real
time. Every door can be tried at http://localhost:8000/docs; changes need the csrf_token of the sign-in answer in
X-CSRF-Token.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime

import uvicorn
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from refund_agent import db as database
from refund_agent.agent.adapters import missing_key, model_adapter
from refund_agent.agent.costs import PRICES
from refund_agent.agent.graph import Agent
from refund_agent.agent.model import ModelAdapter, RecordingAdapter, ScriptedModel
from refund_agent.api import live
from refund_agent.api.app import create_app
from refund_agent.api.auth import set_password
from refund_agent.evaluation.mock_scripts import MOCK
from refund_agent.fixtures import seed
from refund_agent.policy import REPO_ROOT
from refund_agent.scenarios import load_split, policy_for

NAME = "refund_demo_api"
# For the fictional users of the local demo only.
DEMO_PASSWORD = "refund-demo-local"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the HTTP layer on a local demo database.")
    parser.add_argument("--scenario", default="D01", help="development scenario to load (mock mode: one with a script)")
    parser.add_argument("--keep", action="store_true", help="serve the previous run's database instead of a new one")
    parser.add_argument("--live", action="store_true", help="the evaluated agent on a paid model instead of the script")
    parser.add_argument("--model", default="gpt-6.1-sol", choices=sorted(PRICES), help="live mode's model")
    parser.add_argument("--reasoning", default="low", help="live mode's reasoning effort")
    parser.add_argument("--budget-usd", type=float, help="live mode: the most the whole server may spend")
    parser.add_argument(
        "--prices-checked", type=date.fromisoformat, help="live mode: the date the prices were checked, YYYY-MM-DD"
    )
    return parser.parse_args(argv)


def not_ready(args: argparse.Namespace) -> str | None:
    """Why the server cannot start as asked, or None. Live mode needs the owner's explicit budget, the date the
    prices were checked and the model's key (only its presence is checked; it is never read or printed)."""
    scenarios = {s.id for s in load_split("development")}
    if args.scenario not in scenarios:
        return f"no development scenario {args.scenario}"
    if not args.live:
        if args.scenario not in MOCK:
            return f"mock mode has no script for {args.scenario}; choose one of {', '.join(sorted(MOCK))}"
        return None
    if args.budget_usd is None or not 0 < args.budget_usd <= live.MOST_USD:
        return f"live mode needs --budget-usd above 0 and at most {live.MOST_USD:.2f}"
    if args.prices_checked is None or args.prices_checked > date.today():
        return "live mode needs --prices-checked with the date you checked the model's prices (not in the future)"
    key = missing_key(args.model)
    if key:
        return f"no {key} in the environment; run with `uv run --env-file .env ...`"
    return None


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    reason = not_ready(args)
    if reason:
        sys.exit(f"Not started: {reason}")
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

    budget = None
    log = REPO_ROOT / "runs" / f"live-{started.strftime('%Y%m%dT%H%M%SZ')}" / "agent-requests.jsonl"
    model: ModelAdapter
    if args.live:
        budget = live.session_budget(app_engine, args.budget_usd)
        model = RecordingAdapter(model_adapter(args.model, args.reasoning, role="agent", budget=budget), log)
    else:
        model = ScriptedModel(MOCK[scenario.id].agent)

    retried = live.retry_stuck_notices(app_engine) if args.keep else 0
    pool = database.checkpoint_pool("app", NAME)
    agent = Agent(app_engine, policy, model, PostgresSaver(pool), clock)
    emails = {p.id: p.email for p in (*scenario.fixture.customers, *scenario.fixture.staff)}
    print(
        f"Database {NAME} ({'kept' if start else 'new'}): scenario {scenario.id}, business clock from {business_start}"
    )
    print(f"Customer {emails[scenario.customer.id]}, staff {emails[scenario.fixture.staff[0].id]}")
    print(f"Every demo user's password is in {__file__}")
    if budget is not None:
        print(f"Agent: LIVE MODEL {model.name}, configuration A. It costs money.")
        print(
            f"Budget for this server ${budget.limit_usd:.2f}; already spent on this database "
            f"${budget.spent_usd:.4f}; left ${budget.left_usd:.4f}"
        )
        print(f"Prices checked on {args.prices_checked}; every request is written to {log.relative_to(REPO_ROOT)}")
    else:
        print("Agent: the scripted model of mock mode, configuration A (no model is called, nothing is spent)")
    if retried:
        print(f"{retried} staff decision(s) whose delivery to the agent had failed three times get new attempts.")
    print("Payments are simulated in the shop's test ledger; no money moves.")
    print("API documentation: http://localhost:8000/docs")
    try:
        # Plain HTTP on this machine only, so the cookie cannot be marked Secure here; behind HTTPS it must be.
        uvicorn.run(
            create_app(app_engine, policy, clock, secure_cookies=False, agent=agent, deliver_every_s=5, budget=budget),
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
