"""The live pilot on the development scenarios (plan sections 9 to 12). It is the only command that spends money.

    uv run python -m refund_agent.evaluation.pilot --dry-run
    uv run --env-file .env python -m refund_agent.evaluation.pilot --reasoning low --budget-usd 1 --prices-checked DATE

A dry run sends nothing and needs no key. It writes the first request of the agent and of the simulated customer for
D01 to runs/pilot-dry-run/, so each can be read in full, and prints the worst case cost of a whole pilot.

A paid run refuses to start unless docs/pilot/predictions.md is committed and unchanged (the question and the
predictions are written before the run), an OPENAI_API_KEY is present (only its presence is checked; it is never read
or printed), and the date the prices were checked is given. It runs the development scenarios once each in
configuration A, with the agent and the simulated customer on the chosen model, on fresh copies of a migrated
database. It writes the manifest, every request with each of its attempts, and every verdict to
runs/pilot-<time>-<reasoning>/, and stops before any attempt, retries included, that could cross the budget; the try
it stops is still judged on what was done and saved, marked stopped_by_budget, before its database is dropped. The
verdicts stay unknown until a person reads the conversations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from langgraph.checkpoint.postgres import PostgresSaver

from refund_agent import db as database
from refund_agent.agent.costs import PRICES, Budget
from refund_agent.agent.model import RecordingAdapter, load_instructions
from refund_agent.agent.openai_adapter import OpenAIResponses
from refund_agent.agent.tools import tool_definitions
from refund_agent.evaluation import manifest
from refund_agent.evaluation.customers import SIMULATOR_INSTRUCTIONS, SimulatedCustomer, simulator_instructions
from refund_agent.evaluation.runner import RunResult, run_scenario
from refund_agent.policy import REPO_ROOT, load_policy
from refund_agent.scenarios import load_split

PREDICTIONS = REPO_ROOT / "docs" / "pilot" / "predictions.md"
RUNS = REPO_ROOT / "runs"
TEMPLATE, RUN = "refund_pilot_template", "refund_pilot_run"
# Bounds for the worst case estimate of a whole pilot: model requests per scenario.
AGENT_REQUESTS, SIMULATOR_REQUESTS = 12, 8


def _shown(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path)


class NotReady(Exception):
    """A paid run may not start yet; the message says why."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="The live pilot on the development scenarios.")
    parser.add_argument("--dry-run", action="store_true", help="write the first requests to files and send nothing")
    parser.add_argument("--model", default="gpt-6-luna", choices=sorted(PRICES))
    parser.add_argument("--reasoning", default="low", help="the agent's reasoning effort, e.g. low or none")
    parser.add_argument("--simulator-reasoning", default="low", help="the simulated customer's, fixed for a pilot")
    parser.add_argument("--budget-usd", type=float, default=1.0, help="stop before any request that could cross it")
    parser.add_argument(
        "--prices-checked", type=date.fromisoformat, help="the date the prices were checked, YYYY-MM-DD"
    )
    parser.add_argument("--scenarios", default="", help="comma-separated IDs; all development scenarios by default")
    parser.add_argument("--repeats", type=int, default=1, choices=range(1, 6), help="tries per scenario, each fresh")
    return parser.parse_args(argv)


def check_ready(args: argparse.Namespace) -> str:
    """Everything a paid run needs before its first request. Returns the commit that holds the predictions."""
    committed = manifest.git("log", "-1", "--format=%H", "--", str(PREDICTIONS.relative_to(REPO_ROOT)))
    changed = manifest.git("status", "--porcelain", "--", str(PREDICTIONS.relative_to(REPO_ROOT)))
    if not PREDICTIONS.exists() or not committed or changed:
        raise NotReady(f"commit {PREDICTIONS.relative_to(REPO_ROOT)} first: predictions are written before the run")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise NotReady("no OPENAI_API_KEY in the environment; run with `uv run --env-file .env ...`")
    if args.prices_checked is None or args.prices_checked > date.today():
        raise NotReady("give --prices-checked with the date you checked the model's prices (not in the future)")
    if not 0 < args.budget_usd <= 5:
        raise NotReady("the budget must be above 0 and at most the pilot's limit of $5 (plan section 12)")
    return committed


def dry_run(args: argparse.Namespace, scenarios: dict) -> None:
    out = RUNS / "pilot-dry-run"
    out.mkdir(parents=True, exist_ok=True)
    d01 = scenarios["D01"]
    agent = OpenAIResponses(args.model, args.reasoning, role="agent")
    simulator = OpenAIResponses(args.model, args.simulator_reasoning, role="simulator")
    first_agent = agent.request(
        load_instructions().text, [{"role": "customer", "text": d01.customer.opening_message}], tool_definitions()
    )
    seen_by_simulator = [
        {"role": "agent", "text": d01.customer.opening_message, "tool_calls": [], "continuation": []},
        {"role": "customer", "text": "(the agent's first answer would be here)"},
    ]
    first_simulator = simulator.request(simulator_instructions(d01), seen_by_simulator, [])
    for name, request in (("first-agent-request.json", first_agent), ("first-simulator-request.json", first_simulator)):
        (out / name).write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    per_scenario = AGENT_REQUESTS * agent.worst_case_usd(first_agent) * 2  # later requests carry more context
    per_scenario += SIMULATOR_REQUESTS * simulator.worst_case_usd(first_simulator) * 2
    print(f"Wrote {_shown(out)}/first-agent-request.json and first-simulator-request.json; nothing sent.")
    print(f"Agent request: {len(json.dumps(first_agent))} characters, {len(first_agent['tools'])} tools.")
    print(
        f"Worst case for {len(scenarios)} scenarios x {args.repeats} tries with {args.model}: about "
        f"${per_scenario * len(scenarios) * args.repeats:.2f} "
        f"(at most {AGENT_REQUESTS} agent and {SIMULATOR_REQUESTS} simulator requests each, every one at its "
        "maximum output). Real runs cost far less; the budget stops the run either way."
    )


def _save(folder: Path, result: RunResult, attempt: int, spent: dict, counted: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    record = {
        "scenario": result.scenario,
        "try": attempt,
        "configuration": result.configuration,
        "result": result.verdict.result,
        "items": [asdict(item) for item in result.verdict.items],
        "system_error": result.system_error,
        "simulator_error": result.simulator_error,
        "stopped_by_budget": result.stopped_by_budget,
        "agent_requests": result.model_requests,
        "spent_usd": spent,
        "attempts_sent": counted["attempts"],  # every attempt to send a request, retries included
        "uncertain_usd": counted["uncertain_usd"],  # worst cases counted where the charge is unknown
        "messages": result.messages,
    }
    (folder / "result.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False, default=str), encoding="utf-8", newline="\n"
    )


def paid_run(args: argparse.Namespace, scenarios: dict, predictions_commit: str) -> int:
    policy = load_policy()
    started = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RUNS / f"pilot-{started}-{args.model}-{args.reasoning}"
    out.mkdir(parents=True)
    budget = Budget(args.budget_usd)
    identity = {
        "kind": "pilot",
        "model": args.model,
        "agent_reasoning": args.reasoning,
        "simulator_reasoning": args.simulator_reasoning,
        "configuration": "A",
        "repeats": args.repeats,
        "scenarios": sorted(scenarios),
        "prices_usd_per_1m": PRICES[args.model],
        "prices_checked": args.prices_checked.isoformat(),
        "budget_usd": args.budget_usd,
        "agent_instructions_sha256": load_instructions().sha256,
        "simulator_instructions": SIMULATOR_INSTRUCTIONS.relative_to(REPO_ROOT).as_posix(),
        "policy_sha256": policy.content_hash(),
        "predictions_commit": predictions_commit,
    }
    (out / "manifest.json").write_text(json.dumps(manifest.build(identity), indent=2), encoding="utf-8", newline="\n")
    database.create_database(TEMPLATE)
    database.migrate(TEMPLATE)
    print(
        f"Pilot {_shown(out)}: {args.model}, reasoning {args.reasoning}, {args.repeats} tries per scenario, "
        f"budget ${args.budget_usd:.2f}"
    )
    clean: dict[str, int] = {}  # tries without a machine failure or an error, per scenario
    try:
        for scenario_id, attempt in [(s, t) for s in sorted(scenarios) for t in range(1, args.repeats + 1)]:
            scenario, folder = scenarios[scenario_id], out / scenario_id / f"try{attempt}"
            before = dict(budget.by_role)
            attempts_before, uncertain_before = budget.requests, budget.uncertain_usd
            agent = OpenAIResponses(args.model, args.reasoning, role="agent", budget=budget)
            simulator = OpenAIResponses(args.model, args.simulator_reasoning, role="simulator", budget=budget)
            database.create_database(RUN, template=TEMPLATE)
            owner, app = database.engine("owner", RUN), database.engine("app", RUN)
            try:
                with database.checkpoint_connection("app", RUN) as connection:
                    result = run_scenario(
                        scenario,
                        SimulatedCustomer(scenario, RecordingAdapter(simulator, folder / "simulator-requests.jsonl")),
                        RecordingAdapter(agent, folder / "agent-requests.jsonl"),
                        owner=owner,
                        app=app,
                        checkpointer=PostgresSaver(connection),
                        policy=policy,
                    )  # judged before the database is dropped, even when the budget stopped the run
            finally:
                owner.dispose()
                app.dispose()
                database.drop_database(RUN)
            spent = {role: budget.by_role.get(role, 0.0) - before.get(role, 0.0) for role in budget.by_role}
            counted = {
                "attempts": budget.requests - attempts_before,
                "uncertain_usd": budget.uncertain_usd - uncertain_before,
            }
            _save(folder, result, attempt, spent, counted)
            if result.stopped_by_budget:
                print(
                    f"{scenario_id} try {attempt}  STOPPED by the budget before a request: {result.stopped_by_budget}."
                    f" Its result is saved, judged on what was done; nothing later ran."
                )
                return 2
            failed = result.verdict.names("failed")
            errors = [e for e in (result.system_error, result.simulator_error) if e]
            clean[scenario_id] = clean.get(scenario_id, 0) + (not failed and not errors)
            print(
                f"{scenario_id} try {attempt}  {'FAILED: ' + ', '.join(failed) if failed else 'no machine failure'}"
                f"{'; ERROR: ' + '; '.join(errors) if errors else ''}  (${sum(spent.values()):.4f})"
            )
    finally:
        database.drop_database(TEMPLATE)
        print(
            f"Spent about ${budget.spent_usd:.4f} in {budget.requests} attempts, retries included "
            f"({', '.join(f'{r} ${u:.4f}' for r, u in budget.by_role.items())}); of it ${budget.uncertain_usd:.4f} "
            "is the worst case of attempts whose charge is unknown; check the provider's usage page."
        )
    every = [s for s, n in clean.items() if n == args.repeats]
    print(
        f"Without a machine failure in every try: {len(every)} of {len(clean)} scenarios ("
        + ", ".join(f"{s} {n}/{args.repeats}" for s, n in sorted(clean.items()))
        + "). Machine items only, before anyone reads the conversations."
    )
    print("Every verdict is unknown until a person reads the conversations (plan section 9).")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scenarios = {s.id: s for s in load_split("development")}
    if args.scenarios:
        scenarios = {i: scenarios[i] for i in args.scenarios.split(",")}
    if args.dry_run:
        dry_run(args, scenarios)
        return 0
    try:
        commit = check_ready(args)
    except NotReady as reason:
        print(f"Not started: {reason}")
        return 1
    return paid_run(args, scenarios, commit)


if __name__ == "__main__":
    sys.exit(main())
