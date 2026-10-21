"""expiry and a status constraint for visitor messages

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-10 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The four states a message can be in. Phase 5 only ever writes 'pending'; the
# others exist now so the phase-6 send route does not need a migration to record
# what it did.
MESSAGE_STATUSES = ("pending", "sent", "expired", "failed")


def upgrade() -> None:
    """Add expires_at, widen the status column, and constrain the values.

    Three changes, all preparing for phase 6 without implementing it.

    `expires_at` is what makes a draft a bounded capability rather than a
    permanent one. Without it, a token issued today still sends mail next year.

    `status` becomes a constrained enum rather than free text. A typo in the phase-6
    update would otherwise write 'confimed' and the approval route would treat the
    message as still pending forever. The database should refuse that.

    The status column is widened to 20 characters to match the new enum's longest
    value; it was already 20, so this is a no-op in practice and is here to make
    the dependency explicit rather than incidental.
    """
    op.add_column(
        "messages",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Existing rows predate expiry. Backfilling rather than leaving NULL matters:
    # a NULL expires_at would mean "never expires" to every future query, which is
    # the opposite of the intent. Anything already drafted is stale by now.
    op.execute("UPDATE messages SET expires_at = created_at + interval '72 hours'")

    op.alter_column(
        "messages",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    # Created by hand rather than by passing `create_type` to alter_column.
    # ALTER TABLE ... TYPE ... USING casts every existing row against the target
    # type, so the type must already exist when the ALTER runs. Letting SQLAlchemy
    # create it as part of the ALTER is what produced
    # `UndefinedObject: type "message_status" does not exist` on the first attempt.
    # Guarded, because Postgres has no `CREATE TYPE IF NOT EXISTS`. The DO block is
    # the standard idiom for it and makes the migration replayable after a partial
    # run, which is exactly the state this file was written in. Not strictly
    # necessary on a clean chain — `downgrade base` then `upgrade head` works
    # without it — but a migration that cannot be re-run after a failure is a
    # migration that turns a small problem into a large one.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_status') THEN
                CREATE TYPE message_status AS ENUM (
                    'pending', 'sent', 'expired', 'failed'
                );
            END IF;
        END $$;
        """
    )

    op.add_column("messages", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_column("messages", "confirmed_at")

    # The default has to go before the type can change. Postgres refuses to alter a
    # column whose DEFAULT cannot be cast, and `server_default='pending'` is a
    # bare literal that cannot implicitly become 'pending'::message_status.
    #
    # Two steps rather than one because `op.alter_column(..., server_default=...)`
    # emits the new default in the same statement as the type change, which is the
    # statement Postgres rejects. Drop it, alter, set it again.
    op.alter_column("messages", "status", server_default=None)

    # `type_` is the Enum, not a String. Passing String here cast the *values* to
    # the new type but left the column declared as varchar, which Alembic's
    # autogenerate then reported as a pending type change on every run. The type
    # is created by the CREATE TYPE above rather than by SQLAlchemy so it exists
    # before the ALTER tries to cast existing rows against it.
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

    # Partial on pending drafts, which are a tiny fraction of the table and the
    # only rows any query filters for. Written as raw SQL rather than
    # `op.create_index(..., postgresql_where=...)` because Alembic's autogenerate
    # cannot compare a partial index against a model declaration: it sees the
    # single-column form and proposes swapping one for the other on every run.
    op.execute("CREATE INDEX ix_messages_pending ON messages (created_at) WHERE status = 'pending'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_messages_pending")
    op.alter_column("messages", "status", server_default=None)

    op.alter_column(
        "messages",
        "status",
        existing_type=sa.Enum(*MESSAGE_STATUSES, name="message_status"),
        type_=sa.String(length=20),
        existing_nullable=False,
        postgresql_using="status::text",
    )

    op.alter_column("messages", "status", server_default="pending")
    op.add_column("messages", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_column("messages", "sent_at")
    op.drop_column("messages", "expires_at")
    # The type survives the downgrade: rows may hold values only the enum knows,
    # and dropping it would lose the constraint for a rollback that is itself
    # unlikely to be re-upgraded.
