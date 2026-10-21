"""The connection-string rewrite.

Pure string handling, no database, so these run everywhere. The behaviour they
pin is load-bearing on Neon: without it, every async connection raises
`TypeError: connect() got an unexpected keyword argument`, which looks like a
driver bug and is not.
"""

import pytest

from app.core.config import Settings
from app.db.pool import create_engine, normalize_async_url

# Exactly what the Neon console hands out.
NEON_URL = (
    "postgresql+asyncpg://user:pw@ep-x-pooler.r.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)


def test_sslmode_becomes_ssl() -> None:
    """asyncpg spells it `ssl`; `sslmode` is psycopg's spelling."""
    assert "ssl=require" in normalize_async_url(NEON_URL)
    assert "sslmode" not in normalize_async_url(NEON_URL)


def test_channel_binding_is_dropped() -> None:
    """asyncpg negotiates this itself; passing it through is what breaks it."""
    assert "channel_binding" not in normalize_async_url(NEON_URL)


def test_credentials_and_host_survive() -> None:
    normalized = normalize_async_url(NEON_URL)
    assert normalized.startswith("postgresql+asyncpg://user:pw@ep-x-pooler.r.aws.neon.tech/neondb")


def test_other_query_params_are_kept() -> None:
    """Only the two parameters get touched."""
    url = NEON_URL + "&application_name=portfolio"
    normalized = normalize_async_url(url)
    assert "application_name=portfolio" in normalized
    assert "ssl=require" in normalized


def test_channel_binding_only_url_still_works() -> None:
    assert normalize_async_url("postgresql+asyncpg://h/d?channel_binding=require") == (
        "postgresql+asyncpg://h/d"
    )


def test_default_psycopg_url_is_untouched() -> None:
    """A plain `postgresql://` Neon URL selects psycopg, which is libpq.

    Rewriting `sslmode` for it is what produced `invalid connection option
    "ssl"` across every database-backed test on 2026-10-22. The scheme guard
    in `normalize_async_url` is what keeps both drivers honest: this URL must
    reach psycopg byte-for-byte as Neon hands it out.
    """
    psycopg_neon_url = (
        "postgresql://user:pw@ep-x-pooler.r.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require"
    )
    assert normalize_async_url(psycopg_neon_url) == psycopg_neon_url


# --- Engine settings ------------------------------------------------------
#
# These need no database, so they live here rather than in test_pool.py, which is
# integration-marked and therefore skipped on a machine with no credentials.
#
# Both are guesses about somebody else's tier limit, which is exactly the kind of
# value that rots silently. Asserted, so a change to Neon's terms shows up as a
# failing test instead of a flake three weeks later.


def test_connections_recycle_inside_neons_suspend_window() -> None:
    """`pool_recycle` must be *under* 5 minutes, not merely under the old 10.

    Neon suspends the free compute after 5 minutes of inactivity. A connection
    older than that can be handed out with its backend already gone, and the first
    query raises `ConnectionDoesNotExistError` rather than returning an answer.

    Observed as a CI flake that looked like a bug in the send route.
    """
    engine = create_engine(Settings(database_url=NEON_URL))

    assert engine.pool._recycle < 300, (
        f"pool_recycle={engine.pool._recycle}s is not inside Neon's 5-minute free-tier "
        "suspend window; a long test run will see ConnectionDoesNotExistError"
    )


def test_pre_ping_is_on() -> None:
    """The other half of the same protection.

    Pre-ping checks a connection before handing it out, which catches the
    ordinary case. It cannot catch one that dies between the ping and the query,
    which is why `pool_recycle` exists alongside it.
    """
    engine = create_engine(Settings(database_url=NEON_URL))

    assert engine.pool._pre_ping is True


def test_the_pool_is_five_connections_with_no_overflow() -> None:
    """The free plan has 0.25 CU. Five is generous for a portfolio, and
    `max_overflow=0` means a burst cannot open connections the plan cannot hold."""
    engine = create_engine(Settings(database_url=NEON_URL))

    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 0


def test_no_query_string_is_untouched() -> None:
    plain = "postgresql+asyncpg://user:pw@host:5432/db"
    assert normalize_async_url(plain) == plain


def test_sync_url_is_left_for_psycopg() -> None:
    """Only the async URL goes through the `+asyncpg` rewrite.

    Alembic's sync URL keeps `sslmode` and `channel_binding`, which psycopg
    honours; `alembic/env.py` passes `settings.sync_database_url` through
    byte-for-byte. The rewrite only ever touches `+asyncpg` schemes, so a
    Neon-shaped `postgresql://` URL survives it with its security parameters
    intact — even if it were routed through the function by mistake.
    """
    sync_neon_url = (
        "postgresql://user:pw@ep-x-pooler.r.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require"
    )
    assert normalize_async_url(sync_neon_url) == sync_neon_url
