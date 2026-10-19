"""The final evaluation's command without network, key or database: what runs is fixed in the code, the dry run sends
nothing, and a run refuses to start until the held-out set matches its freeze, the targets and the predictions are
committed, the tree is clean, a key is present, the prices were checked and the budget is within the plan's limit."""

import json
from datetime import date

import openai
import pytest

from refund_agent.evaluation import final, manifest
from refund_agent.scenarios import FrozenError, load_split


@pytest.fixture(autouse=True)
def no_openai_client(monkeypatch, tmp_path):
    def refuse(*args, **kwargs):
        raise AssertionError("an OpenAI client was created")

    monkeypatch.setattr(openai, "OpenAI", refuse)
    monkeypatch.setattr(final, "RUNS", tmp_path)
    monkeypatch.setattr(final, "PREDICTIONS", final.TARGETS)  # docs/final/predictions.md may not exist yet
    monkeypatch.setattr(final, "paid_run", lambda *args: pytest.fail("a paid run started"))


def repository(monkeypatch, *, changed_file="", dirty_tree=""):
    """git as the guards see it: every file committed at 0123abcd, unless told otherwise."""

    def git(*args, **kwargs):
        if args[0] == "log":
            return "0123abcd"
        return dirty_tree if "--untracked-files=no" in args else changed_file

    monkeypatch.setattr(manifest, "git", git)


READY = ["--budget-usd", "5", "--prices-checked", "2026-10-19"]


class On19October(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 19)


@pytest.fixture
def ready(monkeypatch):
    repository(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setattr(final, "date", On19October)


def test_what_runs_is_fixed_in_the_code():
    assert {name: vars(setup) for name, setup in final.CONFIGURATIONS.items()} == {
        "A": {"model": "gpt-6-luna", "reasoning": "none", "configuration": "A"},
        "B": {"model": "gpt-6.1-sol", "reasoning": "low", "configuration": "A"},
        "C": {"model": "gpt-6-luna", "reasoning": "none", "configuration": "C"},
    }
    assert vars(final.SIMULATOR) == {"model": "gpt-6-luna", "reasoning": "low", "configuration": "A"}
    assert final.plan(["H02", "H01"])[:4] == [("H01", 1, "A"), ("H01", 1, "B"), ("H01", 1, "C"), ("H01", 2, "A")]
    assert len(final.plan([f"H{n:02d}" for n in range(1, 21)])) == 180


def test_the_dry_run_writes_each_configurations_first_request_and_sends_nothing(tmp_path, capsys):
    assert final.main(["--dry-run"]) == 0
    requests = {
        name: json.loads((tmp_path / "final-dry-run" / f"first-agent-request-{name}.json").read_text(encoding="utf-8"))
        for name in "ABC"
    }
    assert [(r["model"], r["reasoning"]["effort"]) for r in requests.values()] == [
        ("gpt-6-luna", "none"),
        ("gpt-6.1-sol", "low"),
        ("gpt-6-luna", "none"),
    ]
    same = [{k: v for k, v in r.items() if k not in ("model", "reasoning")} for r in requests.values()]
    assert same[0] == same[1] == same[2]  # one prompt and one set of tools for every configuration
    d01 = next(s for s in load_split("development") if s.id == "D01")
    assert requests["A"]["input"][0]["content"] == d01.customer.opening_message  # never a held-out scenario's
    assert "nothing sent" in capsys.readouterr().out


def test_a_held_out_set_that_does_not_match_its_freeze_stops_the_run(ready, monkeypatch, capsys):
    def changed():
        raise FrozenError("changed ['H03-whole-order-partly-returned.toml']")

    monkeypatch.setattr(final, "check_frozen", changed)
    assert final.main(READY) == 1
    assert "H03-whole-order-partly-returned.toml" in capsys.readouterr().out


def test_the_targets_and_the_predictions_must_be_committed(ready, monkeypatch, capsys):
    repository(monkeypatch, changed_file=" M docs/quality-targets.md")
    assert final.main(READY) == 1
    assert "commit docs/quality-targets.md first" in capsys.readouterr().out


def test_the_tree_must_be_clean(ready, monkeypatch, capsys):
    repository(monkeypatch, dirty_tree=" M refund_agent/agent/tools.py")
    assert final.main(READY) == 1
    assert "one identified revision" in capsys.readouterr().out


def test_a_key_must_be_present(ready, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert final.main(READY) == 1
    assert "no OPENAI_API_KEY" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("options", "reason"),
    [
        (["--budget-usd", "5"], "--prices-checked"),
        (["--budget-usd", "5", "--prices-checked", "2026-10-20"], "--prices-checked"),  # tomorrow
        (["--prices-checked", "2026-10-19"], "--budget-usd"),
        (["--prices-checked", "2026-10-19", "--budget-usd", "16"], "at most $15"),
        (["--prices-checked", "2026-10-19", "--budget-usd", "0"], "above 0"),
    ],
)
def test_prices_must_be_checked_and_the_budget_within_the_plans_limit(ready, capsys, options, reason):
    assert final.main(options) == 1
    assert reason in capsys.readouterr().out


def test_when_everything_is_ready_the_run_starts_with_the_commits_it_rests_on(ready, monkeypatch):
    started = []
    monkeypatch.setattr(
        final, "paid_run", lambda args, scenarios, commits: started.append((len(scenarios), commits)) or 0
    )
    assert final.main(READY) == 0
    assert started == [(20, {"targets_commit": "0123abcd", "predictions_commit": "0123abcd"})]
