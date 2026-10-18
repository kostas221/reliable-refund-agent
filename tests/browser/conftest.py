"""Browser tests: the built screens and the HTTP layer on one local server, driven by Playwright in a real browser.

The server runs inside the test process, on a free port and a fresh copy of the template database, with the scripted
agent of mock mode: no API key and no cost. It serves the screens' build from the same origin as the API, as Vite's
proxy does in development, so the session cookie behaves as it does there. The build is made once per session from
the current sources (`npm run build --prefix frontend`), so the tests never drive stale screens.

The browser is the installed Google Chrome; BROWSER_CHANNEL=chromium uses Playwright's own Chromium instead (after
`uv run playwright install chromium`, as CI does). Without a browser or npm the tests are skipped with a message;
REQUIRE_BROWSER=1, as in CI, turns that into a failure.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
import uvicorn
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.postgres import PostgresSaver
from playwright.sync_api import Browser, Error, sync_playwright

from refund_agent import db as database
from refund_agent.agent.graph import Agent
from refund_agent.agent.model import ScriptedModel
from refund_agent.api.app import create_app
from refund_agent.api.auth import set_password
from refund_agent.evaluation.mock_scripts import MOCK
from refund_agent.fixtures import seed
from refund_agent.policy import REPO_ROOT
from tests.acceptance.flows import DEVELOPMENT, POLICY

SCREENS = REPO_ROOT / "frontend" / "dist"
# For the fictional users of these tests only.
PASSWORD = "refund-browser-test"


def unavailable(reason: str) -> None:
    if os.environ.get("REQUIRE_BROWSER") == "1":
        pytest.fail(reason)
    pytest.skip(f"{reason} (REQUIRE_BROWSER=1 turns this skip into a failure)")


@pytest.fixture(scope="session")
def screens() -> None:
    npm = shutil.which("npm")
    if npm is None:
        unavailable("npm is not installed, so the screens cannot be built")
    built = subprocess.run(
        [npm, "run", "build", "--prefix", "frontend"],
        cwd=REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if built.returncode != 0:
        pytest.fail(f"the screens do not build:\n{built.stdout}\n{built.stderr}")


@pytest.fixture(scope="session")
def browser() -> Browser:
    channel = os.environ.get("BROWSER_CHANNEL", "chrome")
    with sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(channel=None if channel == "chromium" else channel)
        except Error as error:
            unavailable(f"Playwright cannot start the browser {channel!r}: {error.message.splitlines()[0]}")
        yield launched
        launched.close()


@dataclass
class Server:
    """One scenario's shop on its own database, served at `url` until `stop`; `start` again is a restart."""

    scenario_id: str
    template: str

    def __post_init__(self) -> None:
        self.scenario = DEVELOPMENT[self.scenario_id]
        self.name = f"refund_browser_{uuid.uuid4().hex[:12]}"
        database.create_database(self.name, template=self.template)
        owner = database.engine("owner", self.name)
        seed(owner, self.scenario, POLICY)
        for person in (*self.scenario.fixture.customers, *self.scenario.fixture.staff):
            set_password(owner, person.id, PASSWORD)
        owner.dispose()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        # The business clock starts at the scenario's time and moves with real time, as in the demo server.
        self.started = datetime.now(UTC)
        self.uvicorn: uvicorn.Server | None = None

    def clock(self) -> datetime:
        return self.scenario.now + (datetime.now(UTC) - self.started)

    def email(self, person_id: str) -> str:
        return next(
            p.email for p in (*self.scenario.fixture.customers, *self.scenario.fixture.staff) if p.id == person_id
        )

    def start(self) -> None:
        self.engine = database.engine("app", self.name)
        self.pool = database.checkpoint_pool("app", self.name)
        model = ScriptedModel(MOCK[self.scenario_id].agent)
        agent = Agent(self.engine, POLICY, model, PostgresSaver(self.pool), self.clock)
        # Notices are also delivered at start and every second, as the demo server does every five.
        app = create_app(self.engine, POLICY, self.clock, secure_cookies=False, agent=agent, deliver_every_s=1)
        app.mount("/", StaticFiles(directory=SCREENS, html=True), name="screens")
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        self.uvicorn = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.uvicorn.run, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 20
        while not self.uvicorn.started:
            if time.monotonic() > deadline:
                raise TimeoutError(f"the test server did not start on port {self.port}")
            time.sleep(0.05)

    def stop(self) -> None:
        if self.uvicorn is not None:
            self.uvicorn.should_exit = True
            self.thread.join(timeout=20)
            self.uvicorn = None
            self.pool.close()
            self.engine.dispose()

    def drop(self) -> None:
        self.stop()
        database.drop_database(self.name)


@pytest.fixture
def serve(template_db, screens):
    """Starts the shop of a development scenario; stopped and dropped after the test."""
    servers: list[Server] = []

    def start(scenario_id: str) -> Server:
        server = Server(scenario_id, template_db)
        servers.append(server)
        server.start()
        return server

    yield start
    for server in servers:
        server.drop()
