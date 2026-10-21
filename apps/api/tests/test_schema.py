"""Schema constraints, checked against the real database.

These are integration tests for the same reason as `test_pool.py`: the things
worth checking about a schema are the constraints, and constraints only exist in
a database. A model assertion would prove the ORM believes something, not that
Postgres enforces it.

Run with: `uv run pytest -m integration`
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not get_settings().database_url,
        reason="DATABASE_URL not set",
    ),
]

# A fixed unit vector keeps the insert deterministic without embedding anything.
UNIT_VECTOR = [0.1] * 384


async def _purge(db, table: str, column: str, value: str) -> None:
    """Delete rows a previous test left behind.

    Table and column names are literals at every call site below, so there is
    no injection surface here; they cannot be bound as parameters in SQL.
    """
    async with db.session_scope() as session:
        await session.execute(
            text(f"DELETE FROM {table} WHERE {column} = :v"),
            {"v": value},
        )


async def _insert_chunk(db, source_path: str, index: int) -> int:
    async with db.session_scope() as session:
        await session.execute(
            text(
                """
                INSERT INTO chunks (source_path, chunk_index, heading, content,
                                    embedding, token_count)
                VALUES (:path, :idx, 'h', 'body', CAST(:vec AS vector), 3)
                RETURNING id
                """
            ),
            {"path": source_path, "idx": index, "vec": str(UNIT_VECTOR)},
        )
        return (await session.execute(text("SELECT max(id) FROM chunks"))).scalar_one()


async def test_chunks_unique_on_source_and_index(ready_db) -> None:
    """Re-ingesting a document must update, not duplicate.

    This constraint is the whole reason the ingest in phase 4 is safe to run
    repeatedly. Without it, every edit to the résumé adds a second copy of the
    same text and retrieval starts returning the same chunk twice.
    """
    path = "test-idempotency.md"
    await _purge(ready_db, "chunks", "source_path", path)

    first = await _insert_chunk(ready_db, path, 0)
    with pytest.raises(IntegrityError):
        await _insert_chunk(ready_db, path, 0)

    await _purge(ready_db, "chunks", "source_path", path)
    assert first is not None


async def test_embedding_is_not_nullable(ready_db) -> None:
    """A row without an embedding must be impossible, not merely unused.

    Nullable embeddings are how a retrieval query silently starts ranking rows
    that were never embedded.
    """
    with pytest.raises(IntegrityError):
        async with ready_db.session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO chunks (source_path, chunk_index, heading, content,
                                        embedding, token_count)
                    VALUES ('test-null.md', 0, 'h', 'body', NULL, 1)
                    """
                )
            )


async def test_message_defaults_to_pending(ready_db) -> None:
    """Nothing is sent until a human approves, and that is the default state.

    `status` is set by the database, not by this INSERT: the statement never
    mentions the column. That is what makes the default true for a psql session
    too. `expires_at` has to be supplied, because it is NOT NULL with no default
    — the expiry is a decision, not an inference.
    """
    async with ready_db.session_scope() as session:
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, approval_token_hash,
                                          origin_ip, expires_at)
                    VALUES ('a', 'a@example.com', 'hi', :h, '127.0.0.1',
                            now() + interval '1 hour')
                    RETURNING id, status
                    """
                ),
                {"h": "0" * 64},
            )
        ).fetchone()

    assert row.status == "pending"

    async with ready_db.session_scope() as session:
        await session.execute(text("DELETE FROM messages WHERE id = :v"), {"v": row.id})


async def test_message_does_not_require_a_plaintext_address(ready_db) -> None:
    """The binding is the salted `ip_hash`, not a stored address.

    `origin_ip` was relaxed to nullable by c3d4e5f6a7b8: the send route compares
    digests (`_ip_matches` on `ip_hash`), so the plaintext form is never read.
    A row the service created has no plaintext address at all — asserted from
    the schema side as "a pending row can exist without one".
    """
    async with ready_db.session_scope() as session:
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status, approval_token_hash,
                                          expires_at)
                    VALUES ('a', 'a@example.com', 'hi', 'pending', :h,
                            now() + interval '1 hour')
                    RETURNING id, status, origin_ip, ip_hash
                    """
                ),
                {"h": "0" * 64},
            )
        ).fetchone()

    assert row.status == "pending"
    assert row.origin_ip is None
    assert row.ip_hash is None  # the schema's legacy shape; the service never writes it

    async with ready_db.session_scope() as session:
        await session.execute(text("DELETE FROM messages WHERE id = :v"), {"v": row.id})


async def test_message_requires_an_expiry(ready_db) -> None:
    """A NULL expires_at would read as 'never expires' to every query."""
    with pytest.raises(IntegrityError):
        async with ready_db.session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status,
                                          approval_token_hash, origin_ip)
                    VALUES ('a', 'a@example.com', 'hi', 'pending', :h, '127.0.0.1')
                    """
                ),
                {"h": "0" * 64},
            )


async def test_cosine_query_returns_ordered_results(ready_db) -> None:
    """The `<=>` operator works against the column as declared.

    Phase 4's retrieval depends on this exact expression. If the operator or the
    dimension were wrong, the failure would be worse rankings rather than an
    error, so it is checked now against real vectors.
    """
    path = "test-cosine.md"
    # Pointing the opposite way, so cosine distance is at its maximum of 2.0.
    # Not a vector of zeros: cosine distance against a zero vector is NaN, which
    # is undefined behaviour in the ranking rather than a distance at all. That
    # is a genuine gotcha for phase 4 — a bad embedding silently poisons the
    # ordering — and it is why the ingest asserts non-zero norms later on.
    far = [-0.1] * 384

    # Clear first: an assertion failure partway through this test skips the
    # cleanup below, and the next run would then collide on the unique
    # constraint instead of testing anything.
    await _purge(ready_db, "chunks", "source_path", path)

    async with ready_db.session_scope() as session:
        await session.execute(
            text(
                """
                INSERT INTO chunks (source_path, chunk_index, heading, content,
                                    embedding, token_count)
                VALUES (:path, 0, 'near', 'near', CAST(:near AS vector), 1),
                       (:path, 1, 'far', 'far', CAST(:far AS vector), 1)
                """
            ),
            {"path": path, "near": str(UNIT_VECTOR), "far": str(far)},
        )

    async with ready_db.session_scope() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT heading, embedding <=> CAST(:q AS vector) AS distance
                    FROM chunks
                    WHERE source_path = :path
                    ORDER BY distance
                    """
                ),
                {"q": str(UNIT_VECTOR), "path": path},
            )
        ).fetchall()

    assert [r.heading for r in rows] == ["near", "far"]
    assert rows[0].distance < rows[1].distance

    await _purge(ready_db, "chunks", "source_path", path)
