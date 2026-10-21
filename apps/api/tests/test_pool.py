"""The async pool, tested against the real Neon project.

These are integration tests and they say so. There is no second database to
point them at: mocking asyncpg would test the mock, and the two things most
likely to break here — the pooled host and scale-to-zero — only exist in the
real thing. They are skipped when DATABASE_URL is absent, so `uv run pytest`
still passes on a machine with no credentials.

Run them with: `uv run pytest -m integration`
"""

import asyncio

import pytest
from sqlalchemy import text

from app.core.config import get_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not get_settings().database_url,
        reason="DATABASE_URL not set; skipping tests that need a real database",
    ),
]


async def test_setup_is_idempotent(ready_db) -> None:
    """Calling setup twice must not leak a second engine."""
    settings = get_settings()
    first = ready_db.get_engine()
    await ready_db.setup(settings)
    assert ready_db.get_engine() is first
    assert ready_db.get_session_factory() is not None


async def test_query_round_trip(ready_db) -> None:
    async with ready_db.session_scope() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


async def test_failed_statement_rolls_back(ready_db) -> None:
    """A failed statement must leave the session usable, not poisoned.

    This matters more than it looks: `session_scope` rolls back on exception,
    and if it did not, every error in a tool would poison the next request on
    that pooled connection.
    """
    from sqlalchemy.exc import ProgrammingError

    with pytest.raises(ProgrammingError):
        async with ready_db.session_scope() as session:
            await session.execute(text("SELECT * FROM table_that_does_not_exist"))

    async with ready_db.session_scope() as session:
        assert (await session.execute(text("SELECT 1"))).scalar_one() == 1


async def test_teardown_disposes_the_pool(ready_db) -> None:
    await ready_db.teardown()
    with pytest.raises(RuntimeError, match="not initialised"):
        ready_db.get_engine()

    # Leave the pool up so the next test in the session is not surprised.
    await ready_db.setup(get_settings())


async def test_neon_reports_its_version(ready_db) -> None:
    """Confirms we are on the real thing, not a local stand-in."""
    async with ready_db.session_scope() as session:
        version = (await session.execute(text("SELECT version()"))).scalar_one()
    assert "PostgreSQL" in version


async def test_vector_extension_is_installed(ready_db) -> None:
    """Phase 4 cannot run without this, and the failure would be cryptic."""
    async with ready_db.session_scope() as session:
        rows = await session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'lakebase_vector'")
        )
    assert rows.scalar_one_or_none() == "lakebase_vector"


async def test_embedding_dimension_matches_the_column(ready_db) -> None:
    """The vector column is 384; the local model must agree.

    A mismatch here is the failure that produces confidently wrong retrieval
    rather than an error, so it is checked against the live schema rather than
    assumed from the migration.
    """
    async with ready_db.session_scope() as session:
        atttypmod = (
            await session.execute(
                text(
                    """
                    SELECT a.atttypmod AS dims
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    WHERE c.relname = 'chunks'
                      AND a.attname = 'embedding'
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                    """
                )
            )
        ).scalar_one()

    assert atttypmod == get_settings().embedding_dimensions


async def test_survives_concurrent_queries(ready_db) -> None:
    """Five pooled connections, used at once, all of them well.

    `max_overflow=0` means a sixth would block. This checks the pool hands out
    what it promised rather than erroring under a tool loop that fans out.
    """

    async def ping() -> bool:
        async with ready_db.session_scope() as session:
            return (await session.execute(text("SELECT true"))).scalar_one()

    results = await asyncio.gather(*[ping() for _ in range(5)])
    assert all(results)
    assert len(results) == 5
