"""Connections to the local PostgreSQL of docker-compose.yml, and database setup for tests and the demo.

Three roles: `admin` creates and drops databases, `owner` runs migrations and loads order data, `app` is what the
application uses. The passwords are local test values from docker-compose.yml and docker/initdb, not secrets.
"""

from __future__ import annotations

import os

import psycopg
from alembic import command
from alembic.config import Config
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy import Engine, create_engine, text

from refund_agent.policy import REPO_ROOT

# The address docker-compose.yml publishes the database on, and only there. "localhost" would try IPv6 (::1) first
# on Windows and wait about three seconds a connection before falling back (2026-10-19).
HOST = os.environ.get("REFUND_DB_HOST", "127.0.0.1")
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
    # LangGraph's checkpoint tables, in the graph schema of migration 0003; its setup is versioned and repeatable.
    with checkpoint_connection("owner", database) as conn:
        PostgresSaver(conn).setup()


def checkpoint_connection(role: str, database: str) -> psycopg.Connection:
    """A connection for LangGraph's PostgresSaver: autocommit and dict rows, as it requires, in the graph schema."""
    user, password = ROLES[role]
    return psycopg.Connection.connect(
        host=HOST,
        port=PORT,
        user=user,
        password=password,
        dbname=database,
        options="-c search_path=graph -c timezone=UTC",
        connect_timeout=3,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )


def checkpoint_pool(role: str, database: str, max_size: int = 10) -> ConnectionPool:
    """Checkpoint connections for a server that answers many conversations at once; same settings as above."""
    user, password = ROLES[role]
    conninfo = make_conninfo(
        host=HOST,
        port=PORT,
        user=user,
        password=password,
        dbname=database,
        options="-c search_path=graph -c timezone=UTC",
        connect_timeout=3,
    )
    kwargs = {"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}
    return ConnectionPool(conninfo, max_size=max_size, kwargs=kwargs, open=True)
