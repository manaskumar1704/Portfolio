"""the one day the visitor's address stops existing

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-10 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MESSAGE_STATUSES = ("pending", "sending", "sent", "expired", "failed")


def upgrade() -> None:
    """Three additive changes. See ADR 0006 for why the order is what it is.

    **origin_ip becomes nullable.** Phase 6 stops writing plaintext addresses,
    but the column stays: dropping it here would break a rollback to the previous
    image, which is still looking for it. It is dropped in a later migration,
    once the new code has run in production.

    **ip_hash is added, nullable.** The salted SHA-256 the send route actually
    compares against. Nullable because existing rows have no hash yet, and
    because `mark_sent` nulls it — a null there means "this row's IP has served
    its purpose", which is different from "never had one".

    **sending is added to the status enum.** The atomic claim moves a row to
    `sending` before the provider call, so a crash during the send leaves a
    traceable state rather than a row that looks forever pending.

    `send_counters` is a single row per day. Resend's free tier allows 100/day;
    the application caps at 70 and this is what makes the cap survive a restart.

    ## Postgres and ALTER TYPE ADD VALUE

    `ALTER TYPE ... ADD VALUE` cannot run inside a transaction block on Postgres
    before version 12. Neon runs 18, so the transaction is fine — but the enum is
    recreated rather than extended so the value ordering stays deterministic and
    the constraint is rebuilt in one statement.
    """
    op.execute("ALTER TABLE messages ALTER COLUMN origin_ip DROP NOT NULL")

    op.add_column("messages", sa.Column("ip_hash", sa.String(length=64), nullable=True))

    # Recreate rather than ADD VALUE: deterministic ordering, one statement, and
    # no dependency on the server version's transaction rules.
    op.execute("DROP TYPE IF EXISTS message_status_old")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_status') THEN
                CREATE TYPE message_status AS ENUM (
                    'pending', 'sending', 'sent', 'expired', 'failed'
                );
            ELSE
                ALTER TYPE message_status ADD VALUE IF NOT EXISTS 'sending';
            END IF;
        END $$;
        """
    )

    op.alter_column("messages", "status", server_default=None)
    op.alter_column(
        "messages",
        "status",
        existing_type=sa.String(length=20),
        type_=sa.Enum(*MESSAGE_STATUSES, name="message_status"),
        existing_nullable=False,
        postgresql_using="status::message_status",
    )
    op.alter_column(
        "messages",
        "status",
        server_default=sa.text("'pending'::message_status"),
    )

    # One row per day. `day` as the primary key is what makes
    # `ON CONFLICT (day) DO UPDATE` the cap check rather than a read-modify-write.
    op.create_table(
        "send_counters",
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("day"),
    )

    # The one index on ip_hash, and it rides on `expires_at` rather than the
    # hash: the sweep's work is "rows that still hold an identifier", ordered by
    # when they stop being needed. An index *on* ip_hash would be for looking a
    # row up by hash, which nothing does — the send route fetches by id and
    # compares in Python.
    op.execute(
        """
        CREATE INDEX ix_messages_retained ON messages (expires_at)
        WHERE ip_hash IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_messages_retained")
    op.drop_table("send_counters")

    op.alter_column("messages", "status", server_default=None)
    op.alter_column(
        "messages",
        "status",
        existing_type=sa.Enum(*MESSAGE_STATUSES, name="message_status"),
        type_=sa.Enum("pending", "sent", "expired", "failed", name="message_status_old"),
        existing_nullable=False,
        postgresql_using="status::message_status_old",
    )
    op.execute("DROP TYPE IF EXISTS message_status_old")

    op.execute("DROP INDEX IF EXISTS ix_messages_ip_hash")
    op.drop_column("messages", "ip_hash")

    # Not restored to NOT NULL: rows whose hash was cleared on send have a null
    # origin_ip, and a NOT NULL constraint would fail on them. A rollback keeps
    # the nullable column rather than destroying data to satisfy a constraint the
    # new code no longer honours.
    op.alter_column("messages", "origin_ip", nullable=True)