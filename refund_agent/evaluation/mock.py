"""Run every development scenario in mock mode and print the verdicts: `uv run python -m refund_agent.evaluation.mock`.

No API key and no cost: the scripted agent and customer of mock_scripts.py drive the real backend, graph and database
(start it first with `docker compose up -d`), each run on a fresh copy of a migrated database. The careless agent
runs in configurations A and C. `--show D02` also prints that scenario's conversation. The output is ASCII.
"""

from __future__ import annotations

import argparse
import json
import uuid

from langgraph.checkpoint.postgres import PostgresSaver

from refund_agent import db as database
from refund_agent.agent.model import ScriptedModel
from refund_agent.evaluation.customers import ScriptedCustomer
from refund_agent.evaluation.mock_scripts import CARELESS_D01, MOCK
from refund_agent.evaluation.runner import CUT_OFF, RunResult, run_scenario
from refund_agent.policy import load_policy
from refund_agent.scenarios import load_split


def _line(result: RunResult, title: str) -> str:
    failed, pending = result.verdict.names("failed"), result.verdict.names("pending")
    untested = result.verdict.names("not_exercised")
    if result.system_error:
        outcome = f"SYSTEM ERROR ({result.system_error})"
    elif failed:
        outcome = "FAILED: " + ", ".join(failed)
    else:
        outcome = f"no failure; {len(pending)} items wait for a person to read it"
    if untested and not result.system_error:
        outcome += "; NOT EXERCISED: " + ", ".join(untested)
    if result.ended in CUT_OFF:
        outcome += f"; CUT OFF: {result.ended}"
    return f"{result.scenario}  {result.configuration}  {title[:44]:<44}  {outcome}"


def _transcript(result: RunResult) -> list[str]:
    lines = []
    for message in result.messages:
        if message["role"] == "customer":
            lines.append(f"  CUSTOMER  {message['text']}")
        elif message["role"] == "event":
            lines.append(f"  (backend) {message['text']}")
        elif message["role"] == "tool":
            answer = json.loads(message["content"])
            short = {k: answer[k] for k in ("refused", "status", "amount_minor", "outcome") if k in answer}
            if "receipt" in answer:
                short["receipt"] = answer["receipt"]["receipt_number"]
            lines.append(f"            <- {message['name']}: {short or 'ok'}")
        elif message.get("tool_calls"):
            call = message["tool_calls"][0]
            lines.append(f"  AGENT     presses {call['name']} {call['arguments']}")
        else:
            lines.append(f"  AGENT     {message['text']}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--show", metavar="ID", help="also print this scenario's conversation, e.g. D02")
    show = parser.parse_args().show
    policy = load_policy()
    scenarios = {s.id: s for s in load_split("development")}
    runs = [(sid, MOCK[sid], "A", scenarios[sid].title) for sid in sorted(MOCK)]
    runs += [("D01", CARELESS_D01, c, "careless agent: pays before any approval") for c in ("A", "C")]
    print("Mock runs: scripted agent and customer, real backend and database, no API calls.\n")
    # Names of this invocation's own, so a run started meanwhile drops none of them (review of 2026-10-19, R7).
    batch = f"refund_mock_{uuid.uuid4().hex[:8]}"
    template, run = f"{batch}_template", f"{batch}_run"
    database.create_database(template)
    database.migrate(template)
    try:
        for scenario_id, mock, configuration, title in runs:
            database.create_database(run, template=template)
            owner, app = database.engine("owner", run), database.engine("app", run)
            try:
                with database.checkpoint_connection("app", run) as connection:
                    result = run_scenario(
                        scenarios[scenario_id],
                        ScriptedCustomer(scenarios[scenario_id], mock.customer),
                        ScriptedModel(mock.agent),
                        owner=owner,
                        app=app,
                        checkpointer=PostgresSaver(connection),
                        policy=policy,
                        configuration=configuration,
                    )
            finally:
                owner.dispose()
                app.dispose()
                database.drop_database(run)
            print(_line(result, title))
            if show == scenario_id and mock is MOCK.get(scenario_id):
                print("\n".join(_transcript(result)) + "\n")
    finally:
        database.drop_database(template)


if __name__ == "__main__":
    main()
