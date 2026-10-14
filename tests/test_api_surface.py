"""The shape of the HTTP layer, without a database: which doors exist and what they accept.

No door proposes or executes a refund, and the server refuses an agent in configuration C, so the lab configuration
cannot be chosen or reached over HTTP (plan section 10.5). Request bodies accept only the sign-in fields, decisions and
the chat text, and every change except signing in needs the CSRF header.
"""

import ast
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine

from refund_agent.api.app import create_app
from refund_agent.policy import REPO_ROOT, load_policy

# Never connects: create_engine only prepares a connection pool.
APP = create_app(
    create_engine("postgresql+psycopg://nobody@localhost:1/none"), load_policy(), lambda: datetime.now(UTC)
)
SPEC = APP.openapi()
CHANGES = {"post", "put", "patch", "delete"}


def operations():
    for path, methods in SPEC["paths"].items():
        for method, operation in methods.items():
            yield path, method, operation


def test_no_door_proposes_or_executes_a_refund():
    for path, method, _ in operations():
        assert "execute" not in path and "propose" not in path and "refund" not in path, (method, path)
    source = (REPO_ROOT / "refund_agent" / "api" / "app.py").read_text(encoding="utf-8")
    imported = {
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module == "refund_agent.refunds"
        for alias in node.names
    }
    assert not imported & {"execute", "propose"}, "the doors must not reach the agent's tools"


def test_request_bodies_accept_only_sign_in_fields_decisions_and_chat_text():
    for name, schema in SPEC["components"]["schemas"].items():
        if name.endswith("Body"):
            assert schema.get("additionalProperties") is False, name
            assert set(schema["properties"]) <= {"email", "password", "decision", "text"}, name


def test_every_change_except_signing_in_needs_the_csrf_header():
    for path, method, operation in operations():
        if method not in CHANGES or (path, method) == ("/api/session", "post"):
            continue
        headers = {p["name"].lower() for p in operation.get("parameters", []) if p["in"] == "header"}
        assert "x-csrf-token" in headers, (method, path)


def test_the_server_refuses_an_agent_in_the_lab_configuration():
    class LabAgent:
        configuration = "C"

    with pytest.raises(ValueError, match="never served over HTTP"):
        create_app(
            create_engine("postgresql+psycopg://nobody@localhost:1/none"), load_policy(), datetime.now, agent=LabAgent()
        )
