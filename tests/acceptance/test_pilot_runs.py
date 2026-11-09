"""The paid pilot's bookkeeping, through refund_agent/evaluation/trials.py, with no model and no key: the runner is
replaced, the databases are real (review of 2026-10-19, R3 and R7). A try writes that it started, saves its result
before its database is dropped, and an unexpected failure keeps its database and is saved; two runs never share a
database."""

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from refund_agent import db as database
from refund_agent.evaluation import mock, pilot, trials
from refund_agent.evaluation.evaluator import Verdict
from refund_agent.evaluation.runner import RunResult
from refund_agent.fixtures import seed
from tests.acceptance.flows import DEVELOPMENT

ARGS = argparse.Namespace(
    model="gpt-6-luna",
    reasoning="none",
    simulator_model="gpt-6-luna",
    simulator_reasoning="low",
    budget_usd=1.0,
    prices_checked=date(2026, 10, 18),
    repeats=1,
)
TWO = {"D01": DEVELOPMENT["D01"], "D04": DEVELOPMENT["D04"]}


def exists(name: str) -> bool:
    engine = database.engine("owner", name)
    try:
        with engine.connect():
            return True
    except OperationalError:
        return False
    finally:
        engine.dispose()


@pytest.fixture
def recorded(monkeypatch, tmp_path, db):
    """The pilot writing into tmp_path; every database it creates and drops, in order; those it left are dropped."""
    monkeypatch.setattr(pilot, "RUNS", tmp_path)
    events: list[tuple[str, str]] = []
    create, drop = database.create_database, database.drop_database
    creating_now = []  # create_database drops a database of the same name first: not a drop of the pilot's

    def creating(name, template=None):
        events.append(("create", name))
        creating_now.append(name)
        try:
            create(name, template=template)
        finally:
            creating_now.pop()

    def dropping(name):
        if not creating_now:
            events.append(("drop", name))
        drop(name)

    monkeypatch.setattr(database, "create_database", creating)
    monkeypatch.setattr(database, "drop_database", dropping)
    yield events
    for name in {name for kind, name in events if kind == "create"}:
        drop(name)


def folder_of(tmp_path, scenario_id: str):
    (run,) = tmp_path.glob("pilot-*")
    return run / scenario_id / "try1"


def test_a_try_that_crashes_is_saved_and_keeps_its_database(recorded, monkeypatch, tmp_path):
    # The try commits something, then fails in a way the runner does not catch.
    def crashing(scenario, customer, model, *, owner, policy, **_):
        seed(owner, scenario, policy)
        raise RuntimeError("the connection to the database was lost")

    monkeypatch.setattr(trials, "run_scenario", crashing)
    assert pilot.paid_run(ARGS, TWO, "abc123") == 3
    folder = folder_of(tmp_path, "D01")
    crash = json.loads((folder / "crash.json").read_text(encoding="utf-8"))
    assert crash["crash"] == "RuntimeError: the connection to the database was lost"
    assert json.loads((folder / "started.json").read_text(encoding="utf-8"))["database"] == crash["kept_database"]
    assert not (folder / "result.json").exists()
    # The evidence is kept: the database exists, with what the try committed.
    kept = database.engine("owner", crash["kept_database"])
    try:
        with kept.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM users")).scalar_one() > 0
    finally:
        kept.dispose()
    assert ("drop", crash["kept_database"]) not in recorded
    # Nothing later ran, and only the template was dropped.
    assert not folder_of(tmp_path, "D01").parent.parent.joinpath("D04").exists()
    template = recorded[0][1]
    assert [name for kind, name in recorded if kind == "drop"] == [template]


def test_a_result_is_saved_before_its_database_is_dropped(recorded, monkeypatch, tmp_path):
    def judged(scenario, customer, model, **_):
        return RunResult(scenario.id, "A", Verdict(scenario.id, ()), [], 0, None)

    saved = []
    save = trials.save_result

    def saving(folder, result, *rest):
        saved.append((result.scenario, len(recorded)))
        save(folder, result, *rest)

    monkeypatch.setattr(trials, "run_scenario", judged)
    monkeypatch.setattr(trials, "save_result", saving)
    assert pilot.paid_run(ARGS, TWO, "abc123") == 0
    template = recorded[0][1]
    d01, d04 = (name for kind, name in recorded if kind == "create" and name != template)
    assert recorded == [
        ("create", template),
        ("create", d01),
        ("drop", d01),
        ("create", d04),
        ("drop", d04),
        ("drop", template),
    ]
    assert saved == [("D01", 2), ("D04", 4)]  # each saved while its database still existed
    assert (folder_of(tmp_path, "D04") / "result.json").exists()


def test_a_failed_save_keeps_the_database(recorded, monkeypatch):
    monkeypatch.setattr(
        trials,
        "run_scenario",
        lambda scenario, *_, **__: RunResult(scenario.id, "A", Verdict(scenario.id, ()), [], 0, None),
    )

    def broken(*_):
        raise OSError("no space left on the disk")

    monkeypatch.setattr(trials, "save_result", broken)
    with pytest.raises(OSError, match="no space"):
        pilot.paid_run(ARGS, TWO, "abc123")
    (kept,) = [name for kind, name in recorded if kind == "create" and not name.endswith("_template")]
    assert exists(kept)


def judged_at_once(scenario, *_, **__):
    return RunResult(scenario.id, "A", Verdict(scenario.id, ()), [], 0, None)


@pytest.mark.parametrize("failures", [1, 99])
def test_a_database_that_cannot_be_dropped_after_its_result_is_saved_does_not_stop_the_run(
    recorded, monkeypatch, tmp_path, failures
):
    # D42 try 2 of 2026-10-23: the result was saved, dropping its database timed out after the computer woke, and the
    # run stopped before try 3. A drop is tried again; a database still not dropped is kept and named, and the run
    # goes on.
    monkeypatch.setattr(trials, "run_scenario", judged_at_once)
    monkeypatch.setattr(trials, "DROP_RETRY_SECONDS", (0, 0, 0))
    drop, left = database.drop_database, {"count": failures}

    def unreachable_at_first(name):
        saved = any(tmp_path.glob("pilot-*/D01/try1/result.json"))  # create_database drops a namesake first
        if "_d01_" in name and saved and left["count"] > 0:
            left["count"] -= 1
            raise OperationalError("DROP DATABASE", {}, Exception("connection timeout expired"))
        drop(name)

    monkeypatch.setattr(database, "drop_database", unreachable_at_first)
    assert pilot.paid_run(ARGS, TWO, "abc123") == 0
    assert (folder_of(tmp_path, "D04") / "result.json").exists()  # the next try ran
    d01 = next(name for kind, name in recorded if kind == "create" and "_d01_" in name)
    kept = folder_of(tmp_path, "D01") / "kept_database.json"
    if failures == 1:  # dropped at the second attempt
        assert not kept.exists() and not exists(d01)
    else:
        assert json.loads(kept.read_text(encoding="utf-8"))["database"] == d01 and exists(d01)


def test_a_paid_run_keeps_the_computer_awake_and_names_the_simulated_customers_model(recorded, monkeypatch, tmp_path):
    monkeypatch.setattr(trials, "run_scenario", judged_at_once)
    entered = []

    @contextmanager
    def awake():
        entered.append(True)
        yield

    monkeypatch.setattr(pilot, "awake", awake)
    assert pilot.paid_run(ARGS, {"D01": DEVELOPMENT["D01"]}, "abc123") == 0
    assert entered == [True]
    (run,) = tmp_path.glob("pilot-*")
    identity = json.loads((run / "manifest.json").read_text(encoding="utf-8"))["identity"]
    assert (identity["model"], identity["simulator_model"]) == ("gpt-6-luna", "gpt-6-luna")


class _OneSecond(datetime):
    """Every call of now() in the same second: two runs started back to back on a fast computer (the first CI run on
    GitHub, 2026-11-08, gave both pilots one folder name, and the second stopped)."""

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 8, 17, 8, 57, tzinfo=tz)


def test_two_pilots_never_share_a_database_or_a_folder(recorded, monkeypatch, tmp_path):
    monkeypatch.setattr(
        trials,
        "run_scenario",
        lambda scenario, *_, **__: RunResult(scenario.id, "A", Verdict(scenario.id, ()), [], 0, None),
    )
    monkeypatch.setattr(pilot, "datetime", _OneSecond)
    pilot.paid_run(ARGS, {"D01": DEVELOPMENT["D01"]}, "abc123")
    pilot.paid_run(ARGS, {"D01": DEVELOPMENT["D01"]}, "abc123")
    first, second = recorded[:4], recorded[4:]  # each: its template and its try, created and dropped
    assert {name for _, name in first}.isdisjoint({name for _, name in second})
    assert sorted(run.name for run in tmp_path.glob("pilot-*")) == [
        "pilot-20261108T170857Z-gpt-6-luna-none",
        "pilot-20261108T170857Z-gpt-6-luna-none-2",
    ]


def test_two_mock_runs_never_share_a_database(recorded, monkeypatch):
    def stop(*_, **__):
        raise KeyboardInterrupt  # cut short at the first try: enough to see the names

    monkeypatch.setattr(mock, "run_scenario", stop)
    monkeypatch.setattr(sys, "argv", ["mock"])
    for _ in range(2):
        with pytest.raises(KeyboardInterrupt):
            mock.main()
    # Each run: its template and its run database, created and dropped.
    first, second = {name for _, name in recorded[:4]}, {name for _, name in recorded[4:]}
    assert len(recorded) == 8 and len(first) == len(second) == 2 and first.isdisjoint(second)
