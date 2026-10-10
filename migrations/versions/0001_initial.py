"""Initial schema: migrations/sql/0001_initial.sql."""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql" / "0001_initial.sql"


def upgrade() -> None:
    # The driver connection runs the whole file, function bodies included, without SQLAlchemy's parameter parsing.
    op.get_bind().connection.driver_connection.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("the initial schema is not downgraded; drop the database instead")
