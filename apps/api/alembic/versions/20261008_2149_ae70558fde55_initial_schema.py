"""initial schema: pgvector extension, four tables, and the ANN index

Revision ID: ae70558fde55
Revises:
Create Date: 2026-10-08 21:49:32.429481
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa

from alembic import op

revision: str = "ae70558fde55"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Must come first: the chunks table below declares a vector column, and
    # Postgres needs the type to exist before the CREATE TABLE runs.
    #
    # `lakebase_vector` is Neon's vector extension. It installs pgvector through
    # CASCADE and adds the `lakebase_ann` index access method, which is what the
    # index at the bottom uses. It relies on a preloaded library Neon enables by
    # default; a project that customised its preload list will fail here, and
    # the fix is in the Neon console rather than in this file.
    op.execute("CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE")

    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("source_path", sa.String(length=512), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=512), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.Vector(dim=384),
            nullable=False,
        ),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # Not decoration: this is what makes re-running the ingest an update
        # rather than a duplicate insert.
        sa.UniqueConstraint("source_path", "chunk_index", name="uq_chunks_source_index"),
    )

    # Nearest-neighbour index over the embeddings. `vector_cosine_ops` pairs with
    # the `<=>` distance operator used in the retrieval query; mixing an operator
    # class and an operator that disagree is the classic silent-wrong-answer
    # bug, because the query still runs and just returns worse matches.
    #
    # `lists = 'auto'` lets the index size its own IVF partition layout from the
    # row count. On a corpus this small the planner prefers an exact scan anyway,
    # so this index is insurance for growth, not a speedup today.
    op.execute(
        """
        CREATE INDEX ix_chunks_embedding_ann ON chunks
          USING lakebase_ann (embedding vector_cosine_ops)
          WITH (build_mode = 'standard')
        """
    )

    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        # 'pending' until a human approves, then 'confirmed'. Anything else is a
        # bug, so phase 6 constrains the value.
        sa.Column("status", sa.String(length=20), nullable=False),
        # A SHA-256 of the token, never the token itself: a leaked row must not be
        # replayable into sending mail.
        sa.Column("approval_token_hash", sa.String(length=64), nullable=False),
        sa.Column("origin_ip", sa.String(length=45), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_id", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        # Phase 6 reads the inbox by status; without this it is a sequential
        # scan of every message ever drafted.
        sa.Index("ix_messages_status", "status"),
    )

    op.create_table(
        "tool_call_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("arguments", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # The evals and any abuse investigation both read this table
        # newest-first.
        sa.Index("ix_tool_call_log_created_at", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("tool_call_log")
    op.drop_table("messages")
    op.drop_table("ingest_runs")
    # The ANN index goes with its table; naming it separately would be a
    # dependency-ordered drop, and this is the only index on the table.
    op.drop_table("chunks")
    # Deliberately not dropping lakebase_vector. Extensions are shared with
    # anything else in this database, and dropping one is harder to undo than
    # leaving it installed.
