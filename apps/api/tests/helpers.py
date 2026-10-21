"""Test helpers for the phase-6 send route.

The send route needs a row that exists with a known token and a known IP. Rather
than duplicating the INSERT in every test, it lives here once.

These helpers do real database work and skip without DATABASE_URL, so they are
integration-shaped even though the tests that use them do not carry the marker.
"""

import asyncio
from dataclasses import dataclass

import pytest

from app.core.client_ip import hash_ip
from app.core.logging import get_logger
from app.db import pool

log = get_logger(__name__)

DEFAULT_SALT = "a-sufficiently-long-test-salt"


async def ensure_pool() -> None:
    """Build the engine if it is not already up.

    `TestClient` runs the app's lifespan on its own event loop, in another thread.
    The engine is a module-level singleton so it survives that, but the ordering
    between pytest-asyncio and a sync fixture is not worth depending on: an async
    test that inserts a row should not care whether the client fixture ran first.
    Idempotent, because `pool.setup` returns early when an engine exists.

    **One retry.** Neon suspends the free compute after five minutes idle, and
    while it is waking, resolving its hostname intermittently fails with
    `socket.gaierror`. That is the free tier's behaviour, not a defect in
    anything under test — but it makes CI flaky, and `autoDeployTrigger:
    checksPass` means a flaky CI blocks deploys.

    The retry is here rather than in `pool.setup` on purpose: in production a
    DNS blip should cost one 500, which is honest, and papering over it in the
    connection path would hide a real outage behind retries.
    """
    from app.core.config import get_settings

    if not get_settings().database_url:
        pytest.skip("DATABASE_URL not set")

    for attempt in range(2):
        try:
            await pool.setup(get_settings())
            return
        except (OSError, ConnectionError, TimeoutError) as exc:
            if attempt == 1:
                raise
            log.warning("connection attempt failed (%s); retrying once", type(exc).__name__)
            await asyncio.sleep(3)


async def teardown_pool() -> None:
    """Dispose the engine. Call from the same loop that used it."""
    await pool.teardown()


@dataclass(frozen=True)
class PendingDraft:
    """A draft row plus the plaintext token that was never stored."""

    id: int
    token: str


async def make_pending_draft(
    IP: str,  # noqa: N803 - matches the env-var spelling used in the tests
    salt: str = DEFAULT_SALT,
    name: str = "Ada Lovelace",
    email: str = "recruiter@example.com",
    body: str = "I would like to talk about a role.",
) -> PendingDraft:
    """Insert a pending draft and return its id and plaintext token.

    The token is generated here rather than by `contact.create_draft` so a test
    can hold it without the service returning it, which is exactly the shape the
    browser gets.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.services.contact import hash_token

    token = "test-token-" + "x" * 32
    expires = datetime.now(UTC) + timedelta(hours=72)

    await ensure_pool()

    async with pool.session_scope() as session:
        row_id = (
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status,
                                          approval_token_hash, ip_hash, expires_at)
                    VALUES (:name, :email, :body, 'pending', :token_hash, :ip_hash, :expires)
                    RETURNING id
                    """
                ),
                {
                    "name": name,
                    "email": email,
                    "body": body,
                    "token_hash": hash_token(token),
                    "ip_hash": hash_ip(IP, salt),
                    "expires": expires,
                },
            )
        ).scalar_one()

    _TEST_IDS.append(row_id)

    return PendingDraft(id=row_id, token=token)


# Every row this module has inserted, so the cleanup below can remove exactly
# those and nothing else. A marker column would be the same idea with an extra
# migration; a marker in `body` would collide with a visitor's actual text.
_TEST_IDS: list[int] = []


async def clear_test_drafts() -> None:
    """Delete every row `make_pending_draft` has created.

    Exact by id, so a run cannot quietly remove a real message. Without this the
    suite leaves hundreds of pending rows behind, which makes the table
    meaningless to look at and gives the retention sweep more work than the real
    site ever would.
    """
    if not _TEST_IDS:
        return

    from sqlalchemy import text

    ids = list(_TEST_IDS)
    _TEST_IDS.clear()

    async with pool.session_scope() as session:
        await session.execute(text("DELETE FROM messages WHERE id = ANY(:ids)"), {"ids": ids})


def pending_ip_hash(ip: str, salt: str = DEFAULT_SALT) -> str:
    """The stored form of an address, for cross-checking both sides.

    `hash_ip` normalises internally, so this is simply the hash. The indirection
    exists so a test can assert "the row and the request agree" without knowing
    which normalisation each side applies.
    """
    return hash_ip(ip, salt)
