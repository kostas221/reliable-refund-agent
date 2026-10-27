"""The customer's decline told to the agent: migrations/sql/0008_decline_notices.sql."""

from pathlib import Path

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql" / "0008_decline_notices.sql"


def upgrade() -> None:
    op.get_bind().connection.driver_connection.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("the schema is not downgraded; drop the database instead")
