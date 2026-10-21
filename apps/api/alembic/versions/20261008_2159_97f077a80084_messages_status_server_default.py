"""give messages.status a database default of 'pending'

Revision ID: 97f077a80084
Revises: ae70558fde55
Create Date: 2026-10-08 21:59:01.008341
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "97f077a80084"
down_revision: str | None = "ae70558fde55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """The column is NOT NULL and previously had only a Python-side default.

    Every write that went through the ORM got 'pending'. Every other writer — a
    psql session, a future admin script, a migration that backfills — got a
    NOT NULL violation. The default belongs in the database, because the
    database is what the constraint lives in.

    Found by test_schema.py, which inserts without naming the column and so
    has to rely on the server default.
    """
    op.alter_column(
        "messages",
        "status",
        existing_type=sa.String(length=20),
        server_default="pending",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "messages",
        "status",
        existing_type=sa.String(length=20),
        server_default=None,
        existing_nullable=False,
    )
