"""hybrid retrieval: lexical + dense, fused with RRF

Revision ID: a1b2c3d4e5f6
Revises: 97f077a80084
Create Date: 2026-10-09 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "97f077a80084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a generated tsvector column and its GIN index.

    Why this migration exists, measured rather than assumed: dense retrieval alone
    cannot tell an on-topic question from an off-topic one on this corpus. Ten
    on-topic questions scored 0.315 to 0.537 best-match cosine distance; eight
    off-topic questions scored 0.406 to 0.600. The ranges overlap, so no distance
    threshold separates them, and `search_portfolio` cannot honestly say "nothing
    matched".

    "What is his email?" is the clearest failure: almost no semantic overlap with
    the contact document, but the exact term is sitting in it. A lexical
    retriever finds that; a dense one cannot.

    ## Why `ts_rank_cd` and not BM25

    The neon-postgres skill's hybrid-search reference prescribes BM25 via
    `CREATE EXTENSION lakebase_bm25`. That is not available here: this project has
    an allowlist, and the attempt failed with

        InsufficientPrivilege: extension "lakebase_bm25" is not in the allowed
        extensions list

    `ts_rank_cd` is built into every Postgres, needs no extension, and is fine at
    this corpus size. BM25 would score better on a large corpus; the upgrade path
    is one operator in `services/rag.py` if the corpus grows past a few hundred
    chunks.

    The column is GENERATED, so it cannot drift from the content it indexes.
    """
    op.execute(
        """
        ALTER TABLE chunks
          ADD COLUMN IF NOT EXISTS body_tsv tsvector
          GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_body_tsv ON chunks USING gin (body_tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_body_tsv")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS body_tsv")
