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
        (["--scenario", "D999"], "no development scenario"),  # D99 exists since 2026-11-04
    ],
)
def test_the_server_refuses_to_start_without_what_it_needs(key, argv, reason):
    assert reason in not_ready(parse_args(argv))


def test_live_mode_without_a_key_is_refused(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert "OPENAI_API_KEY" in not_ready(parse_args(LIVE))


# Serving the screens from the server itself, as the Docker image does (docker-compose.yml, profile app)


def test_the_server_listens_on_this_computer_alone_and_serves_no_screens_by_default(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = parse_args([])
    assert (args.host, args.screens) == ("127.0.0.1", None)


def test_screens_are_served_only_from_a_built_folder(tmp_path):
    assert "npm run build" in not_ready(parse_args(["--screens", str(tmp_path)]))
    (tmp_path / "index.html").write_text("<!doctype html><title>Refunds</title>", encoding="utf-8")
    assert not_ready(parse_args(["--screens", str(tmp_path)])) is None


def test_the_screens_never_hide_a_door_of_the_api(tmp_path):
    """Mounted last, the screens answer every path the API does not hold; every /api door keeps its own answer."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from refund_agent.api.app import with_screens

    (tmp_path / "index.html").write_text("<!doctype html><title>Refunds</title>", encoding="utf-8")
    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    http = TestClient(with_screens(app, tmp_path))
    assert "<title>Refunds</title>" in http.get("/").text
    assert http.get("/api/health").json() == {"status": "ok"}
    assert http.get("/api/no-such-door").status_code == 404
    assert http.get("/no-such-file.js").status_code == 404
