"""What the local server needs before it starts (refund_agent/api/__main__.py): mock mode needs nothing, and live mode,
which costs money, starts only with the owner's budget, the date the prices were checked and a key in the
environment (only its presence is checked)."""

from datetime import date, timedelta

import pytest

from refund_agent.api.__main__ import not_ready, parse_args

LIVE = ["--live", "--budget-usd", "1", "--prices-checked", "2026-11-01"]


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")


def test_mock_mode_is_the_default_and_needs_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = parse_args([])
    assert (args.live, args.scenario) == (False, "D01")
    assert not_ready(args) is None


def test_live_mode_defaults_to_the_products_model(key):
    args = parse_args(LIVE)
    assert (args.model, args.reasoning) == ("gpt-6.1-sol", "low")
    assert not_ready(args) is None


@pytest.mark.parametrize(
    ("argv", "reason"),
    [
        (["--live", "--prices-checked", "2026-11-01"], "--budget-usd"),
        (["--live", "--budget-usd", "0", "--prices-checked", "2026-11-01"], "--budget-usd"),
        (["--live", "--budget-usd", "6", "--prices-checked", "2026-11-01"], "at most 5.00"),
        (["--live", "--budget-usd", "1"], "--prices-checked"),
        (["--live", "--budget-usd", "1", "--prices-checked", str(date.today() + timedelta(days=1))], "prices"),
        (["--scenario", "D99"], "no development scenario"),
    ],
)
def test_the_server_refuses_to_start_without_what_it_needs(key, argv, reason):
    assert reason in not_ready(parse_args(argv))


def test_live_mode_without_a_key_is_refused(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert "OPENAI_API_KEY" in not_ready(parse_args(LIVE))
