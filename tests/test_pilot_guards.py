"""The pilot command without network, key or database: the dry run sends nothing, and a paid run refuses to start until
the predictions are committed, a key is present, the prices were checked and the budget is within the pilot's limit.
"""

import json
from datetime import date, timedelta

import openai
import pytest

from refund_agent.evaluation import manifest, pilot


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


def test_a_paid_run_needs_committed_predictions(monkeypatch, capsys):
    monkeypatch.setattr(manifest, "git", lambda *args, **kwargs: {"log": "0123abcd", "status": " M docs/..."}[args[0]])
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    assert pilot.main(["--prices-checked", date.today().isoformat()]) == 1
    assert "predictions are written before the run" in capsys.readouterr().out


def test_a_paid_run_needs_a_key(committed_predictions, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert pilot.main(["--prices-checked", date.today().isoformat()]) == 1
    assert "no OPENAI_API_KEY" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("options", "reason"),
    [
        ([], "--prices-checked"),
        (["--prices-checked", (date.today() + timedelta(days=1)).isoformat()], "--prices-checked"),
        (["--prices-checked", date.today().isoformat(), "--budget-usd", "6"], "at most the pilot's limit"),
        (["--prices-checked", date.today().isoformat(), "--budget-usd", "0"], "above 0"),
    ],
)
def test_a_paid_run_needs_checked_prices_and_a_budget_within_the_limit(
    committed_predictions, monkeypatch, capsys, options, reason
):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
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
