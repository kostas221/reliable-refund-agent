"""One try of one scenario on a fresh database, with its evidence kept: shared by the development pilot and the final
evaluation, so both follow the same rules (review of 2026-10-19, R3 and R7).

- A batch owns its databases: a migrated template and one copy of it per try, all named after the batch, so a second
  run started meanwhile drops none of them.
- A try writes started.json before it begins, and its result before its database is dropped: a failed save keeps
  the database.
- An unexpected failure (of the harness, the graph or the database) is saved as crash.json, with what was spent, and
  its database is kept for diagnosis. The agent's and the simulator's own failures are not crashes: the runner records
  them in the result.
- A database that cannot be dropped once its try's result is saved is tried again and, if it still cannot be, kept
  and named in kept_database.json; the run goes on, since the try's evidence is saved (D42 try 2 of 2026-10-23: the
  computer slept, the drop timed out on waking, and the run stopped before try 3). awake() keeps Windows from sleeping
  while a run is in progress.
"""

from __future__ import annotations

import ctypes
import json
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy.exc import OperationalError

from refund_agent import db as database
from refund_agent.agent.costs import Budget
from refund_agent.agent.model import ModelAdapter, RecordingAdapter
from refund_agent.evaluation.customers import SimulatedCustomer
from refund_agent.evaluation.runner import RunResult, run_scenario
from refund_agent.policy import Policy
from refund_agent.refunds import Configuration
from refund_agent.scenarios import Scenario

DROP_RETRY_SECONDS = (2, 5, 10)  # waits between attempts to drop a database whose try's result is saved
_ES_CONTINUOUS, _ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


@contextmanager
def awake(setter: Callable[[int], object] | None = None) -> Iterator[None]:
    """Keep Windows from sleeping while the block runs, and allow it again after. Elsewhere it does nothing. setter:
    the system call, SetThreadExecutionState; tests pass a recorder."""
    if setter is None and sys.platform == "win32":
        setter = ctypes.windll.kernel32.SetThreadExecutionState
    if setter is not None:
        setter(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
    try:
        yield
    finally:
        if setter is not None:
            setter(_ES_CONTINUOUS)


def write_json(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str), encoding="utf-8", newline="\n")


class Batch:
    """The databases of one run. Use as a context manager: the template is created on entry and dropped on exit."""

    def __init__(self, prefix: str) -> None:
        self.name = f"{prefix}_{uuid.uuid4().hex[:8]}"
        self.template = f"{self.name}_template"

    def __enter__(self) -> Batch:
        database.create_database(self.template)
        database.migrate(self.template)
        return self

    def __exit__(self, *_: object) -> None:
        database.drop_database(self.template)

    def database_for(self, label: str) -> str:
        return f"{self.name}_{label}".lower()


@dataclass(frozen=True)
class Outcome:
    result: RunResult | None  # None when the try crashed
    crash: str | None
    database: str  # dropped after a saved result, kept after a crash
    spent: dict[str, float]  # by role
    attempts: int  # attempts sent, retries included
    uncertain_usd: float  # worst cases counted where the charge is unknown
    kept: bool = False  # the database could not be dropped after the result was saved, and is kept


def _drop_after_save(run: str, folder: Path) -> bool:
    """Drop the try's database; True when it could not be dropped and is kept, named in kept_database.json."""
    for wait in (*DROP_RETRY_SECONDS, None):
        try:
            database.drop_database(run)
            return False
        except OperationalError as error:
            if wait is None:
                write_json(
                    folder / "kept_database.json", {"database": run, "error": f"{type(error).__name__}: {error}"}
                )
                return True
            time.sleep(wait)
    raise AssertionError("unreachable")


def save_result(folder: Path, result: RunResult, attempt: int, outcome_cost: dict) -> None:
    write_json(
        folder / "result.json",
        {
            "scenario": result.scenario,
            "try": attempt,
            "configuration": result.configuration,
            "result": result.verdict.result,
            "items": [asdict(item) for item in result.verdict.items],
            "system_error": result.system_error,
            "simulator_error": result.simulator_error,
            "stopped_by_budget": result.stopped_by_budget,
            "ended": result.ended,
            "agent_requests": result.model_requests,
            "refusals": result.refusals,
            "handoff_origins": result.handoff_origins,
            "agent_seconds": result.agent_seconds,
            **outcome_cost,
            "messages": result.messages,
        },
    )


def run_try(
    batch: Batch,
    scenario: Scenario,
    attempt: int,
    folder: Path,
    *,
    agent: ModelAdapter,
    simulator: ModelAdapter,
    budget: Budget,
    policy: Policy,
    configuration: Configuration = "A",
    label: str = "",
) -> Outcome:
    """Plays the try and keeps its evidence. label: what tells this try's database apart within the batch."""
    run = batch.database_for(f"{label}{scenario.id}_{attempt}")
    before, attempts_before, uncertain_before = dict(budget.by_role), budget.requests, budget.uncertain_usd
    write_json(folder / "started.json", {"scenario": scenario.id, "try": attempt, "database": run})
    database.create_database(run, template=batch.template)
    owner, app = database.engine("owner", run), database.engine("app", run)
    result, crash = None, None
    try:
        with database.checkpoint_connection("app", run) as connection:
            result = run_scenario(
                scenario,
                SimulatedCustomer(scenario, RecordingAdapter(simulator, folder / "simulator-requests.jsonl")),
                RecordingAdapter(agent, folder / "agent-requests.jsonl"),
                owner=owner,
                app=app,
                checkpointer=PostgresSaver(connection),
                policy=policy,
                configuration=configuration,
            )  # judged before the database is dropped, even when the budget stopped the run
    except Exception as error:  # not the agent's or the simulator's failure, which the runner records
        crash = f"{type(error).__name__}: {error}"
    finally:
        owner.dispose()
        app.dispose()
    outcome = Outcome(
        result,
        crash,
        run,
        {role: budget.by_role.get(role, 0.0) - before.get(role, 0.0) for role in budget.by_role},
        budget.requests - attempts_before,
        budget.uncertain_usd - uncertain_before,
    )
    cost = {"spent_usd": outcome.spent, "attempts_sent": outcome.attempts, "uncertain_usd": outcome.uncertain_usd}
    if crash is not None:
        write_json(
            folder / "crash.json",
            {"scenario": scenario.id, "try": attempt, "crash": crash, "kept_database": run, **cost},
        )
        return outcome
    save_result(folder, result, attempt, cost)  # saved first: a failed save keeps the database
    if _drop_after_save(run, folder):
        return replace(outcome, kept=True)
    return outcome
