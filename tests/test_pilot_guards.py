"""The pilot command without network, key or database: the dry run sends nothing, and a paid run refuses to start until
the predictions are committed, a key is present, the prices were checked and the budget is within the pilot's limit.
"""

import json
from datetime import date

import openai
import pytest

from refund_agent.evaluation import manifest, pilot, trials


@pytest.fixture(autouse=True)
def no_openai_client(monkeypatch, tmp_path):
    def refuse(*args, **kwargs):
        raise AssertionError("an OpenAI client was created")

    monkeypatch.setattr(openai, "OpenAI", refuse)
    monkeypatch.setattr(pilot, "RUNS", tmp_path)
    monkeypatch.setattr(pilot, "paid_run", lambda *args: pytest.fail("a paid run started"))


@pytest.fixture
def committed_predictions(monkeypatch):
    answers = {"log": "0123abcd", "status": ""}
    monkeypatch.setattr(manifest, "git", lambda *args, **kwargs: answers[args[0]])


def test_the_dry_run_writes_the_first_requests_and_sends_nothing(tmp_path, capsys):
    assert pilot.main(["--dry-run"]) == 0
    agent = json.loads((tmp_path / "pilot-dry-run" / "first-agent-request.json").read_text(encoding="utf-8"))
    simulator = json.loads((tmp_path / "pilot-dry-run" / "first-simulator-request.json").read_text(encoding="utf-8"))
    assert (agent["model"], agent["reasoning"], len(agent["tools"])) == ("gpt-6-luna", {"effort": "low"}, 7)
    assert "tools" not in simulator and "Your goal:" in simulator["instructions"]
    assert "nothing sent" in capsys.readouterr().out


def test_the_simulated_customer_keeps_its_model_when_the_agent_changes_model(tmp_path):
    # A comparison of agent models holds the simulated customer fixed (plan section 9); --model used to set both.
    assert pilot.main(["--dry-run", "--model", "gpt-6.1-sol", "--reasoning", "low"]) == 0
    agent = json.loads((tmp_path / "pilot-dry-run" / "first-agent-request.json").read_text(encoding="utf-8"))
    simulator = json.loads((tmp_path / "pilot-dry-run" / "first-simulator-request.json").read_text(encoding="utf-8"))
    assert (agent["model"], agent["reasoning"]) == ("gpt-6.1-sol", {"effort": "low"})
    assert (simulator["model"], simulator["reasoning"]) == ("gpt-6-luna", {"effort": "low"})


def test_the_computer_is_kept_awake_while_the_block_runs_and_released_after():
    # D42 try 2 of 2026-10-23: the computer slept for 117 minutes in the middle of a paid run.
    calls = []
    with trials.awake(setter=calls.append):
        assert calls == [0x80000001]  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    assert calls == [0x80000001, 0x80000000]  # ES_CONTINUOUS alone: sleep allowed again


def test_the_dry_run_reads_the_first_scenario_chosen(tmp_path):
    # A run of D31 to D42 only (2026-10-22) has no D01, which the dry run used to read whatever was chosen.
    assert pilot.main(["--dry-run", "--scenarios", "D33,D31"]) == 0
    agent = json.loads((tmp_path / "pilot-dry-run" / "first-agent-request.json").read_text(encoding="utf-8"))
    assert agent["input"][0]["content"] == "Hi, I posted the linen scarf back last week. Can I have a refund?"


def test_a_paid_run_needs_committed_predictions(monkeypatch, capsys):
    monkeypatch.setattr(manifest, "git", lambda *args, **kwargs: {"log": "0123abcd", "status": " M docs/..."}[args[0]])
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    assert pilot.main(["--prices-checked", date.today().isoformat()]) == 1
    assert "predictions are written before the run" in capsys.readouterr().out


def test_a_paid_run_needs_a_key(committed_predictions, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert pilot.main(["--prices-checked", date.today().isoformat()]) == 1
    assert "no OPENAI_API_KEY" in capsys.readouterr().out


def test_a_paid_run_of_a_claude_agent_needs_both_keys(committed_predictions, monkeypatch, capsys):
    # The agent on Anthropic, the simulated customer still on OpenAI (plan change log, 2026-11-02).
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert pilot.main(["--model", "claude-sonnet-5-5", "--prices-checked", date.today().isoformat()]) == 1
    assert "no ANTHROPIC_API_KEY" in capsys.readouterr().out


def test_the_dry_run_of_a_claude_agent_writes_its_request_and_keeps_the_customers_model(tmp_path):
    assert pilot.main(["--dry-run", "--model", "claude-sonnet-5-5", "--reasoning", "low"]) == 0
    agent = json.loads((tmp_path / "pilot-dry-run" / "first-agent-request.json").read_text(encoding="utf-8"))
    simulator = json.loads((tmp_path / "pilot-dry-run" / "first-simulator-request.json").read_text(encoding="utf-8"))
    assert (agent["model"], agent["output_config"], len(agent["tools"])) == ("claude-sonnet-5-5", {"effort": "low"}, 7)
    assert (simulator["model"], simulator["reasoning"]) == ("gpt-6-luna", {"effort": "low"})


class On14October(date):
    """The pilot's "today", fixed: dates worked out when the tests are collected went stale in a run that crossed
    midnight, and a date one day ahead became today."""

    @classmethod
    def today(cls):
        return cls(2026, 10, 14)


@pytest.mark.parametrize(
    ("options", "reason"),
    [
        ([], "--prices-checked"),
        (["--prices-checked", "2026-10-15"], "--prices-checked"),  # tomorrow
        (["--prices-checked", "2026-10-14", "--budget-usd", "6"], "at most the pilot's limit"),
        (["--prices-checked", "2026-10-14", "--budget-usd", "0"], "above 0"),
    ],
)
def test_a_paid_run_needs_checked_prices_and_a_budget_within_the_limit(
    committed_predictions, monkeypatch, capsys, options, reason
):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setattr(pilot, "date", On14October)
    assert pilot.main(options) == 1
    assert reason in capsys.readouterr().out


def test_when_everything_is_ready_the_paid_run_is_the_next_step(committed_predictions, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    started = []
    monkeypatch.setattr(pilot, "paid_run", lambda args, scenarios, commit: started.append(commit) or 0)
    assert pilot.main(["--prices-checked", date.today().isoformat(), "--scenarios", "D01,D02"]) == 0
    assert started == ["0123abcd"]  # the predictions' commit goes into the run's manifest


def test_the_manifest_fingerprints_the_files_that_decide_a_run():
    hashes = manifest.file_hashes()
    for path in (
        "refund_agent/agent/tools.py",
        "prompts/agent-v1.md",
        "prompts/customer-simulator-v1.md",
        "policies/refund-policy-v1.toml",
        "scenarios/development/D01-single-returned-item.toml",
        "uv.lock",
    ):
        assert path in hashes
    assert manifest.fingerprint(hashes) == manifest.fingerprint(dict(reversed(list(hashes.items()))))


SETUP = (
    "refund_agent/db.py",
    "migrations/env.py",
    "migrations/versions/0006_rejection_reason.py",
    "alembic.ini",
    "docker/initdb/01-roles.sql",
    "pyproject.toml",
    "scenarios/held-out/H01-one-item-of-multi-seller-order.toml",
)


@pytest.mark.parametrize("path", SETUP)
def test_a_change_to_the_code_that_sets_the_database_up_changes_the_fingerprint(tmp_path, path):
    # Review of 2026-10-19, R10: these files decided what a run ran on, yet a change to them left it the same.
    for one in SETUP:
        (tmp_path / one).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / one).write_bytes((manifest.REPO_ROOT / one).read_bytes())
    before = manifest.fingerprint(manifest.file_hashes(tmp_path))
    (tmp_path / path).write_bytes((tmp_path / path).read_bytes() + b"\n# changed\n")
    assert manifest.fingerprint(manifest.file_hashes(tmp_path)) != before


def test_tries_per_scenario_scale_the_worst_case_and_stay_within_bounds(capsys):
    assert pilot.main(["--dry-run"]) == 0
    one = capsys.readouterr().out
    assert pilot.main(["--dry-run", "--repeats", "3"]) == 0
    three = capsys.readouterr().out
    cost = lambda text: float(text.split("about $")[1].split(" ")[0])  # noqa: E731
    assert "x 3 tries" in three and cost(three) == pytest.approx(3 * cost(one), rel=0.02)
    with pytest.raises(SystemExit):
        pilot.parse_args(["--repeats", "9"])


def test_each_line_is_shown_as_soon_as_it_is_printed(monkeypatch):
    # The owner's first Sonnet command (2026-11-03) showed nothing in Git Bash, where the output is a pipe: Python held
    # the lines, and a long run would look as if nothing ran.
    import io
    import sys

    pipe = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    assert pipe.line_buffering is False
    monkeypatch.setattr(sys, "stdout", pipe)
    assert pilot.main(["--dry-run"]) == 0
    assert pipe.line_buffering is True


def test_tries_run_scenario_by_scenario_in_the_order_of_their_numbers():
    # Past D99 (2026-11-04) the names alone would run D100 before D11.
    assert pilot.try_order({"D100": 0, "D11": 0, "D99": 0}, 2) == [
        ("D11", 1),
        ("D11", 2),
        ("D99", 1),
        ("D99", 2),
        ("D100", 1),
        ("D100", 2),
    ]


def test_a_run_started_in_the_same_second_gets_a_folder_of_its_own(tmp_path):
    from refund_agent.evaluation.trials import new_run_folder

    first = new_run_folder(tmp_path / "runs", "pilot-20261108T170857Z-gpt-6-luna-none")
    second = new_run_folder(tmp_path / "runs", "pilot-20261108T170857Z-gpt-6-luna-none")
    third = new_run_folder(tmp_path / "runs", "pilot-20261108T170857Z-gpt-6-luna-none")
    assert [folder.name for folder in (first, second, third)] == [
        "pilot-20261108T170857Z-gpt-6-luna-none",
        "pilot-20261108T170857Z-gpt-6-luna-none-2",
        "pilot-20261108T170857Z-gpt-6-luna-none-3",
    ]
    assert all(folder.is_dir() and not any(folder.iterdir()) for folder in (first, second, third))
