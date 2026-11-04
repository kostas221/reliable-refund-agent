"""The live pilot on the development scenarios (plan sections 9 to 12). It is the only command that spends money.

    uv run python -m refund_agent.evaluation.pilot --dry-run
    uv run --env-file .env python -m refund_agent.evaluation.pilot --reasoning low --budget-usd 1 --prices-checked DATE

A dry run sends nothing and needs no key. It writes the first request of the agent and of the simulated customer for
the first scenario chosen (D01 by default) to runs/pilot-dry-run/, so each can be read in full, and prints an
estimate of a whole pilot's cost.

A paid run refuses to start unless docs/pilot/predictions.md is committed and unchanged (the question and the
predictions are written before the run), an OPENAI_API_KEY is present (only its presence is checked; it is never read
or printed), and the date the prices were checked is given. It runs the development scenarios once each in
configuration A, with the agent and the simulated customer on the chosen model, on fresh copies of a migrated
database. It writes the manifest, every request with each of its attempts, and every verdict to
runs/pilot-<time>-<reasoning>/, and stops before any attempt, retries included, that could cross the budget; the try
it stops is still judged on what was done and saved, marked stopped_by_budget, before its database is dropped. The
verdicts stay unknown until a person reads the conversations.

Every try writes started.json before it begins and its result before its database is dropped. An unexpected failure
(of the harness, the graph or the database) is saved as crash.json with what was spent, its database is kept for
diagnosis, and the run stops; so is a try cut short by Ctrl+C, without a crash record (review of 2026-10-19, R3). The
databases of one run have names of their own, so a second run started meanwhile drops none of them (R7).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from refund_agent.agent.adapters import missing_key, model_adapter
from refund_agent.agent.costs import PRICES, Budget
from refund_agent.agent.model import load_instructions
from refund_agent.agent.openai_adapter import OpenAIResponses
from refund_agent.agent.tools import tool_definitions
from refund_agent.evaluation import manifest
from refund_agent.evaluation.customers import SIMULATOR_INSTRUCTIONS, simulator_instructions
from refund_agent.evaluation.runner import CUT_OFF
from refund_agent.evaluation.trials import Batch, awake, line_by_line, run_try
from refund_agent.policy import REPO_ROOT
from refund_agent.scenarios import id_order, load_split, policy_for

PREDICTIONS = REPO_ROOT / "docs" / "pilot" / "predictions.md"
RUNS = REPO_ROOT / "runs"
# Model requests per scenario in the estimate of a whole pilot's cost: an assumption, not a limit the graph enforces.
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
    parser.add_argument(
        "--simulator-model",
        default="gpt-6-luna",
        choices=sorted(PRICES),
        help="the simulated customer's model, held fixed when agent models are compared",
    )
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
    key = missing_key(args.model, args.simulator_model)
    if key:
        raise NotReady(f"no {key} in the environment; run with `uv run --env-file .env ...`")
    if args.prices_checked is None or args.prices_checked > date.today():
        raise NotReady("give --prices-checked with the date you checked the model's prices (not in the future)")
    if not 0 < args.budget_usd <= 5:
        raise NotReady("the budget must be above 0 and at most the pilot's limit of $5 (plan section 12)")
    return committed


def dry_run(args: argparse.Namespace, scenarios: dict) -> None:
    out = RUNS / "pilot-dry-run"
    out.mkdir(parents=True, exist_ok=True)
    first = scenarios[min(scenarios)]  # the first scenario chosen: D01 unless --scenarios names others
    instructions = load_instructions(policy=policy_for(scenarios.values()))
    agent = model_adapter(args.model, args.reasoning, role="agent")
    simulator = OpenAIResponses(args.simulator_model, args.simulator_reasoning, role="simulator")
    first_agent = agent.request(
        instructions.text, [{"role": "customer", "text": first.customer.opening_message}], tool_definitions()
    )
    seen_by_simulator = [
        {"role": "agent", "text": first.customer.opening_message, "tool_calls": [], "continuation": []},
        {"role": "customer", "text": "(the agent's first answer would be here)"},
    ]
    first_simulator = simulator.request(simulator_instructions(first), seen_by_simulator, [])
    for name, request in (("first-agent-request.json", first_agent), ("first-simulator-request.json", first_simulator)):
        (out / name).write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    per_scenario = AGENT_REQUESTS * agent.worst_case_usd(first_agent) * 2  # later requests carry more context
    per_scenario += SIMULATOR_REQUESTS * simulator.worst_case_usd(first_simulator) * 2
    print(f"Wrote {_shown(out)}/first-agent-request.json and first-simulator-request.json; nothing sent.")
    print(f"Agent request: {len(json.dumps(first_agent))} characters, {len(first_agent['tools'])} tools.")
    print(
        f"Estimate for {len(scenarios)} scenarios x {args.repeats} tries with {args.model}: about "
        f"${per_scenario * len(scenarios) * args.repeats:.2f} if each made {AGENT_REQUESTS} agent and "
        f"{SIMULATOR_REQUESTS} simulator requests, every one at its maximum output. An estimate, not a limit: a "
        "conversation can make more. The budget is what limits spending, checked before every attempt against its "
        "upper bound."
    )


def try_order(scenario_ids, repeats: int) -> list[tuple[str, int]]:
    """Each scenario's tries one after another, the scenarios in the order of their numbers: D99 before D100."""
    return [(s, attempt) for s in sorted(scenario_ids, key=id_order) for attempt in range(1, repeats + 1)]


def paid_run(args: argparse.Namespace, scenarios: dict, predictions_commit: str) -> int:
    policy = policy_for(scenarios.values())
    started = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RUNS / f"pilot-{started}-{args.model}-{args.reasoning}"
    out.mkdir(parents=True)
    budget = Budget(args.budget_usd)
    identity = {
        "kind": "pilot",
        "model": args.model,
        "agent_reasoning": args.reasoning,
        "simulator_model": args.simulator_model,
        "simulator_reasoning": args.simulator_reasoning,
        "configuration": "A",
        "repeats": args.repeats,
        "scenarios": sorted(scenarios, key=id_order),
        "prices_usd_per_1m": PRICES[args.model],
        "simulator_prices_usd_per_1m": PRICES[args.simulator_model],
        "prices_checked": args.prices_checked.isoformat(),
        "budget_usd": args.budget_usd,
        "agent_instructions_sha256": load_instructions(policy=policy).sha256,
        "simulator_instructions": SIMULATOR_INSTRUCTIONS.relative_to(REPO_ROOT).as_posix(),
        "policy_sha256": policy.content_hash(),
        "predictions_commit": predictions_commit,
    }
    (out / "manifest.json").write_text(json.dumps(manifest.build(identity), indent=2), encoding="utf-8", newline="\n")
    print(
        f"Pilot {_shown(out)}: {args.model}, reasoning {args.reasoning}, {args.repeats} tries per scenario, "
        f"budget ${args.budget_usd:.2f}; simulated customer {args.simulator_model}, reasoning "
        f"{args.simulator_reasoning}"
    )
    clean: dict[str, int] = {}  # tries without a machine failure or an error, per scenario
    not_tested = 0  # tries in which an attack planted in the data never reached the agent
    try:
        with Batch("refund_pilot") as batch, awake():
            for scenario_id, attempt in try_order(scenarios, args.repeats):
                outcome = run_try(
                    batch,
                    scenarios[scenario_id],
                    attempt,
                    out / scenario_id / f"try{attempt}",
                    agent=model_adapter(args.model, args.reasoning, role="agent", budget=budget),
                    simulator=OpenAIResponses(
                        args.simulator_model, args.simulator_reasoning, role="simulator", budget=budget
                    ),
                    budget=budget,
                    policy=policy,
                )
                if outcome.crash is not None:
                    print(
                        f"{scenario_id} try {attempt}  CRASHED: {outcome.crash}. Saved in crash.json; its database "
                        f"{outcome.database} is kept for diagnosis; nothing later ran."
                    )
                    return 3
                result = outcome.result
                if result.stopped_by_budget:
                    print(
                        f"{scenario_id} try {attempt}  STOPPED (the budget or the provider's credit): "
                        f"{result.stopped_by_budget}. Its result is saved, judged on what was done; nothing later ran."
                    )
                    return 2
                failed, untested = result.verdict.names("failed"), result.verdict.names("not_exercised")
                errors = [e for e in (result.system_error, result.simulator_error) if e]
                clean[scenario_id] = clean.get(scenario_id, 0) + (not failed and not errors)
                not_tested += bool(untested)
                print(
                    f"{scenario_id} try {attempt}  {'FAILED: ' + ', '.join(failed) if failed else 'no machine failure'}"
                    f"{'; NOT EXERCISED: ' + ', '.join(untested) if untested else ''}"
                    f"{'; CUT OFF: ' + result.ended if result.ended in CUT_OFF else ''}"
                    f"{'; ERROR: ' + '; '.join(errors) if errors else ''}  (${sum(outcome.spent.values()):.4f})"
                    f"{'; its database could not be dropped and is kept: ' + outcome.database if outcome.kept else ''}"
                )
    finally:
        print(
            f"Spent about ${budget.spent_usd:.4f} in {budget.requests} attempts, retries included "
            f"({', '.join(f'{r} ${u:.4f}' for r, u in budget.by_role.items())}); of it ${budget.uncertain_usd:.4f} "
            "is the worst case of attempts whose charge is unknown; check the provider's usage page."
        )
    every = [s for s, n in clean.items() if n == args.repeats]
    print(
        f"Without a machine failure in every try: {len(every)} of {len(clean)} scenarios ("
        + ", ".join(f"{s} {clean[s]}/{args.repeats}" for s in sorted(clean, key=id_order))
        + "). Machine items only, before anyone reads the conversations."
    )
    if not_tested:
        print(f"In {not_tested} tries an attack planted in the shop's data never reached the agent: not a test of it.")
    print("Every verdict is unknown until a person reads the conversations (plan section 9).")
    return 0


def main(argv: list[str] | None = None) -> int:
    line_by_line()
    args = parse_args(argv)
    scenarios = {s.id: s for s in load_split("development")}
    if args.scenarios:
        scenarios = {i: scenarios[i] for i in args.scenarios.split(",")}
    try:
        policy_for(scenarios.values())
    except ValueError as reason:
        print(f"Not started: {reason}")
        return 1
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
