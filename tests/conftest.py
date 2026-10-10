"""Database fixtures: one migrated template database per test session, and a fresh copy of it for every test.

Without a reachable PostgreSQL (`docker compose up -d`) the database tests are skipped with a message; with
REQUIRE_DB=1, as in CI, a missing database is a failure instead.
"""

import os
import uuid

import pytest
from sqlalchemy.exc import OperationalError

from refund_agent import db as database

TEMPLATE = "refund_template"


@pytest.fixture(scope="session")
def template_db():
    try:
        database.create_database(TEMPLATE)
    except OperationalError:
        if os.environ.get("REQUIRE_DB") == "1":
            raise
        pytest.skip(
            f"PostgreSQL is not reachable on {database.HOST}:{database.PORT}; start it with `docker compose up -d` "
            "(REQUIRE_DB=1 turns this skip into a failure)"
        )
    database.migrate(TEMPLATE)
    yield TEMPLATE
    database.drop_database(TEMPLATE)


@pytest.fixture
def db(template_db):
    name = f"refund_test_{uuid.uuid4().hex[:12]}"
    database.create_database(name, template=template_db)
    engines = []

    def engine(role: str):
        created = database.engine(role, name)
        engines.append(created)
        return created

    yield engine
    for created in engines:
        created.dispose()
    database.drop_database(name)
