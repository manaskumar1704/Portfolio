"""the draft lifecycle: cancelled becomes a state, the form gains context

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-21 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mirrors app/db/models.py. `alembic check` compares the two; they must agree.
MESSAGE_STATUSES = ("pending", "sending", "sent", "expired", "failed", "cancelled")


def upgrade() -> None:
    """`cancelled` joins the status enum; the contact form gains context fields.

    **cancelled** is a visitor's own withdrawal of a draft, through the cancel
    route, while it was still pending. It is a distinct state from `expired`
    (the server's backstop) and from `failed` (the provider's answer): retention
    treats it like a closed draft, and the UI may tell the visitor their
    withdrawal was recorded rather than lost.

    **company / role / subject** are the POST /messages/drafts form's context
    fields. All nullable: the model-facing `draft_message` tool takes none of
    them, so chat-created drafts leave them unset.
    """
    # Recreate pattern from c3d4e5f6a7b8: guarded create on a clean chain,
    # ADD VALUE on a partially-run one. `cancelled` appends last, matching the
    # tuple order, and no existing value is renamed, so the ALTER below can cast
    # every row.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_status') THEN
                CREATE TYPE message_status AS ENUM (
                    'pending', 'sending', 'sent', 'expired', 'failed', 'cancelled'
                );
            ELSE
                ALTER TYPE message_status ADD VALUE IF NOT EXISTS 'cancelled';
            END IF;
        END $$;
        """
    )

    # The column already declares `message_status`; the value list is what
    # changed. Restating the type with the new tuple keeps the model, this
    # file, and the database legible as one shape. The default references the
    # type by name and survives both orderings.
    op.alter_column(
        "messages",
        "status",
        existing_type=sa.Enum(
            "pending", "sending", "sent", "expired", "failed", name="message_status"
        ),
        type_=sa.Enum(*MESSAGE_STATUSES, name="message_status"),
        existing_nullable=False,
    )

    op.add_column("messages", sa.Column("company", sa.String(length=200), nullable=True))
    op.add_column("messages", sa.Column("role", sa.String(length=200), nullable=True))
    op.add_column("messages", sa.Column("subject", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "subject")
    op.drop_column("messages", "role")
    op.drop_column("messages", "company")

    # 'cancelled' exists only in the newer type; a row holding it would fail the
    # cast below. Re-labelled rather than deleted: the row's content is a
    # visitor's words and the older enum has no honest place for it — 'expired',
    # "no longer approvable", is the closest the rollback can say. Deliberate
    # data change, like c3d4e5f6a7b8 keeping a renamed type to avoid exactly this.
    op.execute("UPDATE messages SET status = 'expired' WHERE status = 'cancelled'")

    # Text round-trip, not enum -> enum: Postgres permits NO cast between two
    # distinct enum types, `USING status::other_enum` fails both ways, so the
    # type swap goes through text — the varchar -> enum move is the same one
    # c3d4e5f6a7b8's upgrade makes. The re-labelled values above are all legal
    # labels of both tuples.
    # ix_messages_pending (b2c3d4e5f6a7's upgrade) pins its predicate to the
    # message_status type; altering the column revalidates it and dies there.
    # Dropped around the swap and put back afterwards in b2c3's exact form.
    op.execute("DROP INDEX IF EXISTS ix_messages_pending")
    op.execute("ALTER TABLE messages ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE messages ALTER COLUMN status TYPE text USING status::text")
    op.execute("DROP TYPE message_status")
    op.execute(
        "CREATE TYPE message_status AS ENUM ('pending','sending','sent','expired','failed')"
    )
    op.execute(
        "ALTER TABLE messages "
        "ALTER COLUMN status TYPE message_status USING status::message_status"
    )
    op.execute(
        "ALTER TABLE messages ALTER COLUMN status SET DEFAULT 'pending'::message_status"
    )
    op.execute(
        "CREATE INDEX ix_messages_pending ON messages (created_at) WHERE status = 'pending'"
    )
