"""Connections to the local PostgreSQL of docker-compose.yml, and database setup for tests and the demo.

Three roles: `admin` creates and drops databases, `owner` runs migrations and loads order data, `app` is what the
application uses. The passwords are local test values from docker-compose.yml and docker/initdb, not secrets.
"""

from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from refund_agent.policy import REPO_ROOT

HOST = os.environ.get("REFUND_DB_HOST", "localhost")
PORT = int(os.environ.get("REFUND_DB_PORT", "5433"))
ROLES = {
    "admin": ("postgres", "postgres"),
    "owner": ("refund_owner", "refund_owner"),
    "app": ("refund_app", "refund_app"),
}


def url(role: str, database: str) -> str:
    user, password = ROLES[role]
    return f"postgresql+psycopg://{user}:{password}@{HOST}:{PORT}/{database}"


def engine(role: str, database: str) -> Engine:
    # Every session works in UTC, so timestamptz values come back as UTC datetimes.
    return create_engine(url(role, database), connect_args={"options": "-c timezone=UTC", "connect_timeout": 3})


def _admin(sql: str) -> None:
    admin = create_engine(url("admin", "postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
    try:
        with admin.connect() as conn:
            conn.execute(text(sql))
    finally:
        admin.dispose()


def create_database(name: str, template: str | None = None) -> None:
    """Create an empty database, or a copy of `template`, owned by refund_owner. An existing one is dropped first."""
    drop_database(name)
    copy = f" TEMPLATE {template}" if template else ""
    _admin(f"CREATE DATABASE {name} OWNER refund_owner{copy}")


def drop_database(name: str) -> None:
    _admin(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


def migrate(database: str) -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url("owner", database))
    command.upgrade(config, "head")
