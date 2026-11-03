"""The final evaluation (plan sections 10 to 12): a frozen held-out set, its configurations, three tries each.

    uv run python -m refund_agent.evaluation.final --dry-run
    uv run --env-file .env python -m refund_agent.evaluation.final --set held_out_v1_3 --budget-usd 6 \\
        --prices-checked DATE
    uv run --env-file .env python -m refund_agent.evaluation.final --set held_out_v1_3 \\
        --resume runs/comparison-v1.3-... --budget-usd 6 --prices-checked DATE

What runs is fixed in this module, not chosen on the command line: the named set's group of configurations
(GROUPS: A, B and C for the final evaluations of v1 to v1.2; A and B for the comparison of v1.3), the simulated
customer, three tries of each scenario. For each scenario and try the configurations run one after another, so the
pairs that are compared ran under the same conditions. The one choice is the set, by name (SETS), recorded in the
manifest with the SHA-256 of its freeze, so that a run of another set can never be reported as this one
(docs/held-out-v1.2/protocol.md, section 5). The sets of v1, v1.1 and v1.2, and v1.2's stress set, are spent: their
runs are recorded in SETS, and the runner refuses them.

A run refuses to start unless its set matches its freeze, the set's quality targets and predictions are committed
and unchanged, no tracked file has uncommitted changes (the evaluation runs one identified revision), the key of every
model the set's configurations and the simulated customer use is present (never read or printed), the date the prices
were checked is given, and the budget is within the plan's $15 for a final batch.

It writes runs/<prefix>-<time>/ (SETS): manifest.json, invocations.jsonl (each start and resume, with its budget),
and one folder per configuration with a manifest of its own, laid out as a pilot's (<scenario>/try<n>/), so the
transcripts and the dialogue audit read it unchanged. Each try follows refund_agent/evaluation/trials.py: started.json
first, the result saved before its database is dropped, a crash saved and its database kept.

A run cut short resumes with --resume: tries with a result or a crash record are never run again (no retry until a
success appears, plan section 11); a try that started and has neither was cut short, and is moved aside and run
again. A resume refuses if the code or the settings differ from the run's manifest. The budget counts what the run
spent before, read from its request logs.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
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
from refund_agent.evaluation.sets import SETS
from refund_agent.evaluation.trials import Batch, awake, line_by_line, run_try, write_json
from refund_agent.policy import REPO_ROOT
from refund_agent.refunds import Configuration
from refund_agent.scenarios import (
    FROZEN,
    SPLIT_DIRS,
    FrozenError,
    check_frozen,
    file_sha256,
    load_split,
    policy_for,
)


@dataclass(frozen=True)
class Setup:
    model: str
    reasoning: str
    configuration: Configuration  # A: every check of execute_refund; C: the lab configuration (plan section 10.5)


# The final evaluations of v1 to v1.2.
CONFIGURATIONS = {
    "A": Setup("gpt-6-luna", "none", "A"),  # the product: the setting chosen in the development pilot
    "B": Setup("gpt-6.1-sol", "low", "A"),  # the stronger model with the same checks; Sol takes no "none"
    "C": Setup("gpt-6-luna", "none", "C"),  # the product's model with the selected checks off
}
# The comparison of v1.3 (docs/held-out-v1.3/protocol.md, section 4; plan change log, 2026-11-02): the product's model
# against an Anthropic model, both with every check and the agent of the freeze. A is the product, so the report's
# "B minus A" is Sonnet minus Sol.
COMPARISON = {
    "A": Setup("gpt-6.1-sol", "low", "A"),  # the product's model (plan change log, 2026-11-01)
    "B": Setup("claude-sonnet-5-5", "low", "A"),  # the comparison's second model, effort low
}
GROUPS = {"final": CONFIGURATIONS, "comparison": COMPARISON}
SIMULATOR = Setup("gpt-6-luna", "low", "A")  # the same simulated customer for every configuration
REPEATS = 3
MAX_BUDGET_USD = 15.0  # plan section 12: the first final batch


RUNS = REPO_ROOT / "runs"
# Assumed model requests per conversation for the dry run's estimate: not a limit the graph enforces.
AGENT_REQUESTS, SIMULATOR_REQUESTS = 12, 8


class NotReady(Exception):
    """The final evaluation may not start yet; the message says why."""


def configurations_of(held_out: str) -> dict[str, Setup]:
    """The configurations that run the named set."""
    return GROUPS[SETS[held_out].configurations]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="The final evaluation on the frozen held-out set.")
    parser.add_argument("--dry-run", action="store_true", help="write the first requests to files and send nothing")
    parser.add_argument(
        "--budget-usd", type=float, help=f"stop before any attempt that could cross it (at most {MAX_BUDGET_USD:g})"
    )
    parser.add_argument(
        "--prices-checked", type=date.fromisoformat, help="the date the prices were checked, YYYY-MM-DD"
    )
    parser.add_argument("--resume", type=Path, help="the folder of a run that was cut short")
    parser.add_argument("--set", choices=sorted(SETS), help="the frozen held-out set to run, by name")
    return parser.parse_args(argv)


def _shown(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path)


def _committed(path: Path) -> str:
    """The commit that last changed the file; refuses a file that is missing, never committed or changed since."""
    relative = str(path.relative_to(REPO_ROOT))
    commit = manifest.git("log", "-1", "--format=%H", "--", relative)
    if not path.exists() or not commit or manifest.git("status", "--porcelain", "--", relative):
        raise NotReady(f"commit {_shown(path)} first: it is written before the run")
    return commit


def check_ready(args: argparse.Namespace) -> dict:
    """Everything the final evaluation needs before its first request. Returns the commits it rests on."""
    if args.set is None:
        raise NotReady(f"give --set with the held-out set to run: {', '.join(sorted(SETS))}")
    chosen = SETS[args.set]
    if chosen.spent:
        raise NotReady(chosen.spent)
    try:
        check_frozen(SPLIT_DIRS[chosen.split])
    except FrozenError as error:
        raise NotReady(str(error)) from None
    commits = {"targets_commit": _committed(chosen.targets), "predictions_commit": _committed(chosen.predictions)}
    if manifest.git("status", "--porcelain", "--untracked-files=no"):
        raise NotReady("commit every change first: the final evaluation runs one identified revision")
    key = missing_key(SIMULATOR.model, *(setup.model for setup in configurations_of(args.set).values()))
    if key:
        raise NotReady(f"no {key} in the environment; run with `uv run --env-file .env ...`")
    if args.prices_checked is None or args.prices_checked > date.today():
        raise NotReady("give --prices-checked with the date you checked the models' prices (not in the future)")
    if args.budget_usd is None or not 0 < args.budget_usd <= MAX_BUDGET_USD:
        raise NotReady(f"give --budget-usd above 0 and at most ${MAX_BUDGET_USD:g}, the plan's first final batch")
    return commits


def identity(scenarios: dict, commits: dict, prices_checked: date, held_out: str) -> dict:
    """What the run is: compared on resume, apart from the date the prices were checked."""
    configurations = configurations_of(held_out)
    models = sorted({setup.model for setup in (*configurations.values(), SIMULATOR)})
    return {
        "kind": "final",
        "set": held_out,
        "configurations": {name: vars(setup) for name, setup in configurations.items()},
        "simulator": vars(SIMULATOR),
        "repeats": REPEATS,
        "scenarios": sorted(scenarios),
        "order": f"for each scenario, for each try: {', '.join(configurations)}",
        "prices_usd_per_1m": {model: PRICES[model] for model in models},
        "prices_checked": prices_checked.isoformat(),
        "agent_instructions_sha256": load_instructions(policy=policy_for(scenarios.values())).sha256,
        "simulator_instructions": SIMULATOR_INSTRUCTIONS.relative_to(REPO_ROOT).as_posix(),
        "policy_sha256": policy_for(scenarios.values()).content_hash(),
        "frozen_sha256": file_sha256(SPLIT_DIRS[SETS[held_out].split] / FROZEN),
        "retry_policy": "a try with a result or a crash record is never run again; a try cut short runs again",
        **commits,
    }


def _comparable(record: dict) -> dict:
    """As saved: tuples, such as the prices, compare as the lists JSON turns them into."""
    record = json.loads(json.dumps(record))
    return {
        "identity": {key: value for key, value in record["identity"].items() if key != "prices_checked"},
        "fingerprint": record["fingerprint"],
    }


def _spent_before(out: Path) -> tuple[float, dict[str, float]]:
    """What the run's earlier invocations spent, from every attempt in its request logs."""
    total, by_role = 0.0, {"agent": 0.0, "simulator": 0.0}
    for log in out.rglob("*-requests.jsonl"):
        role = "agent" if log.name.startswith("agent") else "simulator"
        for line in log.read_text(encoding="utf-8").splitlines():
            usd = sum(attempt["usd"] for attempt in json.loads(line).get("attempts", []))
            total, by_role[role] = total + usd, by_role[role] + usd
    return total, by_role


def _configuration_manifest(record: dict, name: str) -> dict:
    """What the transcripts and the audit read for one configuration's folder."""
    ident = record["identity"]
    setup = configurations_of(ident["set"])[name]
    return {
        "identity": {
            "kind": "final",
            "set": ident["set"],
            "configuration": setup.configuration,
            "configuration_name": name,
            "model": setup.model,
            "agent_reasoning": setup.reasoning,
            "simulator_reasoning": SIMULATOR.reasoning,
            "repeats": ident["repeats"],
            "scenarios": ident["scenarios"],
        },
        "git_commit": record["git_commit"],
        "fingerprint": record["fingerprint"],
    }


def _open(args: argparse.Namespace, scenarios: dict, commits: dict) -> Path:
    """The run's folder, new or resumed, with its manifests."""
    record = manifest.build(identity(scenarios, commits, args.prices_checked, args.set))
    if args.resume:
        out = args.resume
        saved = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        if _comparable(saved) != _comparable(record):
            raise NotReady(f"{_shown(out)} ran other code or settings; it can be resumed only by the same revision")
    else:
        out = RUNS / f"{SETS[args.set].prefix}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        out.mkdir(parents=True)
        write_json(out / "manifest.json", record)
        for name in configurations_of(args.set):
            write_json(out / name / "manifest.json", _configuration_manifest(record, name))
    with (out / "invocations.jsonl").open("a", encoding="utf-8", newline="\n") as log:
        started = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "resumed": bool(args.resume)}
        entry = {**started, "budget_usd": args.budget_usd, "prices_checked": args.prices_checked.isoformat()}
        log.write(json.dumps({**entry, "git_commit": record["git_commit"]}) + "\n")
    return out


def plan(scenario_ids: list[str], names: tuple[str, ...] = tuple(CONFIGURATIONS)) -> list[tuple[str, int, str]]:
    return [(s, t, c) for s in sorted(scenario_ids) for t in range(1, REPEATS + 1) for c in names]


def paid_run(args: argparse.Namespace, scenarios: dict, commits: dict) -> int:
    policy = policy_for(scenarios.values())
    out = _open(args, scenarios, commits)
    before, by_role = _spent_before(out)
    budget = Budget(args.budget_usd, spent_usd=before, by_role=by_role)
    configurations = configurations_of(args.set)
    trials = plan(list(scenarios), tuple(configurations))
    print(
        f"Final evaluation {_shown(out)}: {len(trials)} conversations, budget ${args.budget_usd:.2f}"
        + (f", ${before:.4f} spent before" if before else "")
    )
    machine_clean = {name: 0 for name in configurations}
    try:
        with Batch("refund_final") as batch, awake():  # the run lasts hours; a sleeping computer once cost a try
            for scenario_id, attempt, name in trials:
                folder = out / name / scenario_id / f"try{attempt}"
                if (folder / "result.json").exists() or (folder / "crash.json").exists():
                    continue
                if (folder / "started.json").exists():  # cut short: kept aside, then run again
                    aside = 1 + sum(1 for _ in folder.parent.glob(f"try{attempt}-cut-short-*"))
                    folder.rename(folder.with_name(f"try{attempt}-cut-short-{aside}"))
                setup = configurations[name]
                outcome = run_try(
                    batch,
                    scenarios[scenario_id],
                    attempt,
                    folder,
                    agent=model_adapter(setup.model, setup.reasoning, role="agent", budget=budget),
                    simulator=OpenAIResponses(SIMULATOR.model, SIMULATOR.reasoning, role="simulator", budget=budget),
                    budget=budget,
                    policy=policy,
                    configuration=setup.configuration,
                    label=f"{name}_",
                )
                line = f"{scenario_id} try {attempt} {name}"
                if outcome.crash is not None:
                    print(f"{line}  CRASHED: {outcome.crash}. Saved; its database {outcome.database} is kept.")
                    return 3
                result = outcome.result
                if result.stopped_by_budget:
                    print(
                        f"{line}  STOPPED (the budget or the provider's credit): {result.stopped_by_budget}. "
                        "Saved; nothing later ran."
                    )
                    return 2
                failed = result.verdict.names("failed")
                errors = [e for e in (result.system_error, result.simulator_error) if e]
                machine_clean[name] += not failed and not errors
                print(
                    f"{line}  {'FAILED: ' + ', '.join(failed) if failed else 'no machine failure'}"
                    f"{'; CUT OFF: ' + result.ended if result.ended in CUT_OFF else ''}"
                    f"{'; ERROR: ' + '; '.join(errors) if errors else ''}  (${sum(outcome.spent.values()):.4f})"
                )
    finally:
        print(
            f"Spent about ${budget.spent_usd:.4f} in all, retries included "
            f"({', '.join(f'{r} ${u:.4f}' for r, u in budget.by_role.items())}); of it ${budget.uncertain_usd:.4f} "
            "in this invocation is the worst case of attempts whose charge is unknown; check the provider's usage page."
        )
    print(
        "Without a machine failure, this invocation: "
        + ", ".join(f"{name} {count}" for name, count in machine_clean.items())
        + ". Every verdict is unknown until the dialogue audit (plan section 9)."
    )
    return 0


def dry_run(names: tuple[str, ...] = ("held_out_v1_3",)) -> None:
    """The first request of each configuration's agent and of the simulated customer, on D01 (a development
    scenario: nothing of the held-out set is read but its files' names, to count them), and an estimate of the cost
    of running the named sets, which share one group of configurations."""
    groups = {SETS[name].configurations for name in names}
    if len(groups) != 1:
        raise ValueError(f"the sets {', '.join(names)} are run by different configurations")
    configurations = GROUPS[groups.pop()]
    out = RUNS / "final-dry-run"
    out.mkdir(parents=True, exist_ok=True)
    d01 = next(s for s in load_split("development") if s.id == "D01")
    opening = [{"role": "customer", "text": d01.customer.opening_message}]
    simulator = OpenAIResponses(SIMULATOR.model, SIMULATOR.reasoning, role="simulator")
    seen = [{"role": "agent", "text": d01.customer.opening_message, "tool_calls": [], "continuation": []}]
    simulator_request = simulator.request(simulator_instructions(d01), seen, [])
    write_json(out / "first-simulator-request.json", simulator_request)
    scenarios = sum(len(list(SPLIT_DIRS[SETS[n].split].glob("*.toml"))) for n in names)
    conversations = scenarios * REPEATS
    total = 0.0
    for name, setup in configurations.items():
        agent = model_adapter(setup.model, setup.reasoning, role="agent")
        request = agent.request(load_instructions(policy=policy_for([d01])).text, opening, tool_definitions())
        write_json(out / f"first-agent-request-{name}.json", request)
        per = 2 * (
            AGENT_REQUESTS * agent.worst_case_usd(request)
            + SIMULATOR_REQUESTS * simulator.worst_case_usd(simulator_request)
        )
        total += per * conversations
        print(
            f"{name}: {setup.model}, reasoning {setup.reasoning}, configuration {setup.configuration}; "
            f"estimate ${per * conversations:.2f} for {conversations} conversations"
        )
    print(
        f"Wrote {_shown(out)}/: the first agent request of each configuration and the simulator's; nothing sent. "
        f"Estimate for {', '.join(names)}, {conversations * len(configurations)} conversations: about ${total:.2f}, "
        f"if each made {AGENT_REQUESTS} agent and "
        f"{SIMULATOR_REQUESTS} simulator requests at their maximum output. An estimate, not a limit; the budget, "
        "checked before every attempt against its upper bound, is what limits spending."
    )


def main(argv: list[str] | None = None) -> int:
    line_by_line()
    args = parse_args(argv)
    if args.dry_run:
        dry_run((args.set,) if args.set else ("held_out_v1_3",))
        return 0
    try:
        commits = check_ready(args)
    except NotReady as reason:
        print(f"Not started: {reason}")
        return 1
    scenarios = {s.id: s for s in load_split(SETS[args.set].split)}
    try:
        return paid_run(args, scenarios, commits)
    except NotReady as reason:
        print(f"Not started: {reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
