"""The async engine, created once.

Neon's pooled endpoint fronts Postgres with PgBouncer, so this pool holds a
handful of psycopg async connections and Neon decides how many real backends
that becomes. Pointing at the direct endpoint instead would consume one of the 97
usable Postgres connections per process, which is how a free-tier project ends
up refusing connections at inconvenient times.

`pool_pre_ping` earns its place on Neon specifically: the compute suspends
after five idle minutes, and a pooled connection that was open across that
suspension is dead. Without the ping, the first request after a quiet spell
gets an `InterfaceError` instead of an answer.
"""

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

if sys.platform == "win32":
    # The async engine runs on psycopg, whose async driver refuses the
    # ProactorEventLoop that Windows makes default. Anything that opens a
    # connection with this module — uvicorn's dev server, the MCP server, the
    # test suite — inherits the selector loop from here, so there is one
    # place to set it and no caller can forget. Linux, the only platform
    # this code ships on, never evaluates this branch.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def normalize_async_url(url: str) -> str:
    """Adapt a connection string to whichever async driver the URL selects.

    This is driver-dependent, and that is the whole point. `create_async_engine`
    resolves a plain `postgresql://` URL to **psycopg**, which is a libpq
    client: it wants `sslmode` exactly as Neon writes it and honours
    `channel_binding` itself. Rewriting either raises `invalid connection
    option "ssl"` — observed 2026-10-22 as "migrations healthy, every
    database-backed test erroring at once". Only an explicit
    `postgresql+asyncpg://` URL selects asyncpg, which spells TLS `ssl=` and
    does not accept `channel_binding` — the case the rewrite was written for.

    - asyncpg explicit scheme: `sslmode=require` becomes `ssl=require`, and
      `channel_binding` is dropped, because passing it through is what breaks
      the connection.
    - psycopg (the default, and the driver this project ships on): the URL is
      returned untouched.

    Alembic's sync URL is handled elsewhere and keeps both parameters.
    """
    if "+asyncpg" not in url:
        return url
    url = url.replace("sslmode=", "ssl=")
    return _drop_param(url, "channel_binding")


def _drop_param(url: str, name: str) -> str:
    """Remove one query parameter, keeping the rest of the string intact."""
    if f"{name}=" not in url:
        return url
    head, _, query = url.partition("?")
    kept = [pair for pair in query.split("&") if pair and not pair.startswith(f"{name}=")]
    return f"{head}?{'&'.join(kept)}" if kept else head


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the engine. Called once from the lifespan, not at import."""
    return create_async_engine(
        normalize_async_url(settings.database_url),
        pool_size=5,
        # The free plan has 0.25 CU (about 1 GB). Five connections is generous
        # for a portfolio; more just holds memory the container does not have.
        max_overflow=0,
        pool_pre_ping=True,
        # Recycle well inside Neon's idle window, not just inside it.
        #
        # Neon's free tier suspends the compute after 5 minutes of inactivity.
        # `pool_recycle` is the age at which a connection is discarded on checkout,
        # so setting it above that window means a connection can be handed out
        # after the backend behind it has already been suspended — and the first
        # query on it raises `ConnectionDoesNotExistError` rather than returning an
        # answer. Observed as a CI flake that turned out to be this.
        #
        # `pool_pre_ping` is what catches the ordinary case; it cannot catch a
        # connection that dies between the ping and the query, and a long test run
        # or a slow container gives that window time to be hit.
        #
        # 240s keeps every pooled connection comfortably younger than the 5-minute
        # suspend. It costs a reconnect every four minutes on a quiet site, which
        # is a TCP handshake to a server that is already awake.
        pool_recycle=240,
        echo=False,
    )


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("engine not initialised; call setup() in the lifespan")
    return _engine


def get_session_factory() -> async_sessionmaker:
    if _session_factory is None:
        raise RuntimeError("session factory not initialised; call setup() in the lifespan")
    return _session_factory


async def setup(settings: Settings) -> None:
    global _engine, _session_factory
    if _engine is not None:
        # Idempotent on purpose. The lifespan calls it on every boot, and a
        # second call would replace the engine out from under any request still
        # holding a session from the first one.
        return
    _engine = create_engine(settings)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    log.info("database engine ready")


async def teardown() -> None:
    """Close every pooled connection. Called on shutdown.

    Render replaces the container on redeploy, so a leaked socket only wastes
    the old container's life. But without this, a test that creates and drops
    the engine repeatedly leaks file handles until the process complains.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        log.info("database engine disposed")
    _engine = None
    _session_factory = None


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """A session that commits on success and rolls back on any exception.

    Used as `async with session_scope() as session:`. The commit is on the way
    out of the block, so a body that adds rows and returns early still writes
    them, and a body that raises leaves nothing behind.
    """
    session = get_session_factory()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
