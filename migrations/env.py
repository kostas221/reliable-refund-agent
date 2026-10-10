"""Alembic environment: applies the migrations to the URL that refund_agent.db.migrate() sets."""

from alembic import context
from sqlalchemy import create_engine

if context.is_offline_mode():
    raise RuntimeError("offline migrations are not used; run them against a database")

engine = create_engine(context.config.get_main_option("sqlalchemy.url"))
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
