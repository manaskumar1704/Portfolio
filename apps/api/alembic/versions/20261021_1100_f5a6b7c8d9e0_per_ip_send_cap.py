"""the counter that remembers a connection for one day

Revision ID: f5a6b7c8d9e0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-21 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """`ip_send_counters` (ADR 0011).

    Same one-row-per-actor-descriptor shape as `send_counters`, primary key
    `(day, ip_hash)` so `INSERT ... ON CONFLICT (day, ip_hash) DO UPDATE ...
    WHERE count < :cap` is the cap check itself. The `ip_hash` string holds the
    salted digest from ADR 0006 — it is the value `messages.ip_hash` carried,
    kept here for one UTC day and deleted by retention after that.
    """
    op.create_table(
        "ip_send_counters",
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("day", "ip_hash"),
    )


def downgrade() -> None:
    # The table is a counter and holds nothing a rollback needs to preserve.
    op.drop_table("ip_send_counters")
