"""The final evaluation's run and its resume, with no model and no key: the runner is replaced, the databases are real.
Two development scenarios stand in for the held-out set of v1.1, which is never run here, and a stand-in hash for its
freeze, which is written only after the owner approves the set.

Every try runs once, in order, with its configuration's model and checks; a run cut short resumes without running a
finished or crashed try again; a resume by other code is refused; and the budget counts what was spent before."""

import argparse
import json
from contextlib import contextmanager
from datetime import date

import pytest

from refund_agent import db as database
from refund_agent.evaluation import final, trials
from refund_agent.evaluation.evaluator import Verdict
from refund_agent.evaluation.runner import RunResult
from tests.acceptance.flows import DEVELOPMENT

TWO = {"D01": DEVELOPMENT["D01"], "D04": DEVELOPMENT["D04"]}
COMMITS = {"targets_commit": "0123abcd", "predictions_commit": "0123abcd"}


def args(resume=None, budget=5.0):
    return argparse.Namespace(budget_usd=budget, prices_checked=date(2026, 10, 19), resume=resume, set="held_out_v1_1")


@pytest.fixture
def played(monkeypatch, tmp_path, db):
    """The run writing into tmp_path; each try's (scenario, try, model, reasoning, checks); databases left dropped."""
    monkeypatch.setattr(final, "RUNS", tmp_path)
    monkeypatch.setattr(final, "file_sha256", lambda path: f"stand-in for {path.parent.name}/{path.name}")
    calls, stop = [], {}
    created = []
    create = database.create_database

    def creating(name, template=None):
        created.append(name)
        create(name, template=template)

    def fake(scenario, customer, model, *, configuration, **_):
        attempt = sum(1 for c in calls if c[0] == scenario.id and c[3:] == (model.inner.model, configuration)) + 1
        calls.append((scenario.id, attempt, len(calls), model.inner.model, configuration))
        if stop.get("at") == len(calls):
            raise stop["error"]
        return RunResult(scenario.id, configuration, Verdict(scenario.id, ()), [], 1, None)

    monkeypatch.setattr(database, "create_database", creating)
    monkeypatch.setattr(trials, "run_scenario", fake)
    yield calls, stop
    for name in created:
        database.drop_database(name)


def the_run(tmp_path):
    (run,) = tmp_path.glob("final-*")
    return run


def test_every_try_runs_once_in_order_with_its_configuration(played, tmp_path):
    calls, _ = played
    assert final.paid_run(args(), TWO, COMMITS) == 0
    models = {"A": ("gpt-6-luna", "A"), "B": ("gpt-6.1-sol", "A"), "C": ("gpt-6-luna", "C")}
    assert [(s, t, models_of) for s, t, _, *models_of in calls] == [
        (s, t, list(models[c])) for s, t, c in final.plan(list(TWO))
    ]
    run = the_run(tmp_path)
    for scenario, attempt, name in final.plan(list(TWO)):
        assert (run / name / scenario / f"try{attempt}" / "result.json").exists()
    configuration = json.loads((run / "B" / "manifest.json").read_text(encoding="utf-8"))["identity"]
    assert (configuration["model"], configuration["agent_reasoning"], configuration["repeats"]) == (
        "gpt-6.1-sol",
        "low",
        3,
    )
    invocations = (run / "invocations.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["resumed"] for line in invocations] == [False]
    # The run names its set, in its folder and its manifest, with the hash of the set's freeze.
    identity = json.loads((run / "manifest.json").read_text(encoding="utf-8"))["identity"]
    assert run.name.startswith("final-v1.1-")
    assert (identity["set"], identity["frozen_sha256"]) == ("held_out_v1_1", "stand-in for held-out-v1.1/FROZEN")
    assert configuration["set"] == "held_out_v1_1"


def test_a_run_cut_short_resumes_without_running_a_finished_try_again(played, tmp_path):
    calls, stop = played
    stop.update(at=5, error=KeyboardInterrupt())  # D01 try 2, configuration B, cut short
    with pytest.raises(KeyboardInterrupt):
        final.paid_run(args(), TWO, COMMITS)
    run = the_run(tmp_path)
    cut = run / "B" / "D01" / "try2"
    assert (cut / "started.json").exists() and not (cut / "result.json").exists()

    stop.clear()
    calls.clear()
    assert final.paid_run(args(resume=run), TWO, COMMITS) == 0
    assert len(calls) == 18 - 4  # the four finished tries are not run again; the cut one is
    assert (run / "B" / "D01" / "try2-cut-short-1" / "started.json").exists()
    assert (cut / "result.json").exists()
    assert [json.loads(line)["resumed"] for line in (run / "invocations.jsonl").read_text().splitlines()] == [
        False,
        True,
    ]


def test_a_crashed_try_is_kept_and_never_run_again(played, tmp_path):
    calls, stop = played
    stop.update(at=2, error=RuntimeError("the database went away"))
    assert final.paid_run(args(), TWO, COMMITS) == 3
    run = the_run(tmp_path)
    assert json.loads((run / "B" / "D01" / "try1" / "crash.json").read_text())["crash"].startswith("RuntimeError")
    stop.clear()
    calls.clear()
    assert final.paid_run(args(resume=run), TWO, COMMITS) == 0
    crashed = run / "B" / "D01" / "try1"
    assert (crashed / "crash.json").exists() and not (crashed / "result.json").exists()  # recorded, not run again
    assert len(calls) == 18 - 2


def test_a_resume_by_other_code_or_settings_is_refused(played, tmp_path, monkeypatch):
    assert final.paid_run(args(), {"D01": TWO["D01"]}, COMMITS) == 0
    run = the_run(tmp_path)
    monkeypatch.setitem(final.CONFIGURATIONS, "B", final.Setup("gpt-6.1-sol", "medium", "A"))
    with pytest.raises(final.NotReady, match="other code or settings"):
        final.paid_run(args(resume=run), {"D01": TWO["D01"]}, COMMITS)


def test_the_budget_of_a_resume_counts_what_was_spent_before(played, tmp_path, monkeypatch):
    calls, stop = played
    stop.update(at=2, error=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        final.paid_run(args(), {"D01": TWO["D01"]}, COMMITS)
    run = the_run(tmp_path)
    log = run / "A" / "D01" / "try1" / "agent-requests.jsonl"
    log.write_text(json.dumps({"attempts": [{"usd": 0.30}, {"usd": 0.15}]}) + "\n", encoding="utf-8")
    seen = []
    budget = final.Budget

    def remembering(limit, **kwargs):
        made = budget(limit, **kwargs)
        seen.append(made)
        return made

    monkeypatch.setattr(final, "Budget", remembering)
    final.paid_run(args(resume=run, budget=1.0), {"D01": TWO["D01"]}, COMMITS)
    assert seen[0].spent_usd == pytest.approx(0.45) and seen[0].by_role["agent"] == pytest.approx(0.45)


def test_a_final_run_keeps_the_computer_awake(played, monkeypatch, tmp_path):
    # As the pilot since 2026-10-23, when a sleeping computer cost a try: the final evaluation runs for hours.
    entered = []

    @contextmanager
    def awake():
        entered.append("in")
        yield
        entered.append("out")

    monkeypatch.setattr(final, "awake", awake)
    assert final.paid_run(args(), {"D01": TWO["D01"]}, COMMITS) == 0
    assert entered == ["in", "out"]
