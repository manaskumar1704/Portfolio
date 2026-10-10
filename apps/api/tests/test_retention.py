"""What the sweep deletes, and what it deliberately leaves.

No mocks: the sweep is four `DELETE ... WHERE` statements, and the only way to
know a predicate is right is to put rows on both sides of it and check which
side survived.

The advisory lock gets its own test because "only one process sweeps" is a claim
that is trivially true when nothing is running concurrently, which is the only
state a normal test run is in.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.retention import sweep_once
from tests.helpers import clear_test_drafts, ensure_pool, teardown_pool

pytestmark = pytest.mark.asyncio

DAYS_AGO = timedelta(days=1)


def ago(**kwargs) -> datetime:
    return datetime.now(UTC) - timedelta(**kwargs)


async def insert(**overrides) -> int:
    """Insert a message row with overridable ages and statuses."""
    from sqlalchemy import text

    from app.db import pool
    from tests.helpers import _TEST_IDS

    defaults = {
        "status": "pending",
        "created_at": ago(days=30),
        "expires_at": ago(days=1),
        "sent_at": None,
        "ip_hash": "a" * 64,
        "name": "Ada",
        "email": "ada@example.com",
        "body": "Hi",
    }
    defaults.update(overrides)

    async with pool.session_scope() as session:
        row_id = (
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status,
                                          approval_token_hash, ip_hash,
                                          created_at, expires_at, sent_at)
                    VALUES (:name, :email, :body, :status, 'retention-test',
                            :ip_hash, :created_at, :expires_at, :sent_at)
                    RETURNING id
                    """
                ),
                defaults,
            )
        ).scalar_one()

    _TEST_IDS.append(row_id)
    return row_id


async def status_of(message_id: int) -> str | None:
    from sqlalchemy import text

    from app.db import pool

    async with pool.session_scope() as session:
        return (
            await session.execute(
                text("SELECT status FROM messages WHERE id = :id"), {"id": message_id}
            )
        ).scalar_one_or_none()


@pytest.fixture(autouse=True)
async def _database():
    """A live engine, disposed on the way out.

    Every pytest-asyncio test gets a fresh event loop and pooled connections
    belong to the loop that opened them, so the engine has to be built and
    dropped inside the same test. See the same reasoning in `test_send_route.py`.
    """
    await ensure_pool()
    try:
        yield
    finally:
        await clear_test_drafts()
        await teardown_pool()


async def test_an_expired_pending_draft_is_deleted() -> None:
    """The main job. A draft nobody approved should not sit forever."""
    row = await insert(status="pending", created_at=ago(days=30), expires_at=ago(days=1))

    result = await sweep_once(settings())

    assert result.expired_drafts >= 1
    assert await status_of(row) is None


async def test_a_stuck_sending_row_is_deleted_once_expired() -> None:
    """A crash during the send leaves `sending`, and it must not be permanent."""
    row = await insert(status="sending", created_at=ago(days=30), expires_at=ago(days=1))

    await sweep_once(settings())

    assert await status_of(row) is None


async def test_an_unexpired_draft_survives() -> None:
    """The sweep must not delete a draft a visitor is still going to approve."""
    row = await insert(
        status="pending", created_at=ago(hours=2), expires_at=datetime.now(UTC) + timedelta(hours=2)
    )

    await sweep_once(settings())

    assert await status_of(row) == "pending"


async def test_an_unexpired_draft_past_the_retention_window_is_deleted() -> None:
    """The backstop.

    A draft can be written with an expiry far in the future, and if a bug or a
    hand-edited row ever produced one, the age rule still removes it.
    """
    row = await insert(
        status="pending", created_at=ago(days=40), expires_at=datetime.now(UTC) + timedelta(days=30)
    )

    result = await sweep_once(settings(draft_retention_days=7))

    assert result.stale_drafts >= 1
    assert await status_of(row) is None


async def test_a_recently_sent_row_survives() -> None:
    """Sending keeps the row, and clears the hash. A visitor may dispute a send,
    so the record outlives the identifier in it."""
    row = await insert(status="sent", ip_hash=None, sent_at=ago(days=2), created_at=ago(days=2))

    await sweep_once(settings())

    assert await status_of(row) == "sent"


async def test_an_old_sent_row_is_deleted() -> None:
    row = await insert(status="sent", ip_hash=None, sent_at=ago(days=40), created_at=ago(days=40))

    result = await sweep_once(settings(sent_row_retention_days=30))

    assert result.old_sent >= 1
    assert await status_of(row) is None


async def test_a_failed_row_ages_out_like_a_sent_one() -> None:
    """`sent_at` is null for a row that never sent, so it ages from `created_at`."""
    row = await insert(
        status="failed", sent_at=None, created_at=ago(days=40), expires_at=ago(days=40)
    )

    result = await sweep_once(settings(sent_row_retention_days=30))

    assert result.old_sent >= 1
    assert await status_of(row) is None


async def test_the_sweep_does_not_touch_an_orphan_hash_on_a_live_row() -> None:
    """A row still holding a hash but otherwise current keeps both.

    Clearing the hash is `mark_sent`'s job, at the exact moment it stops being
    needed. The sweep deleting rows is a separate concern; doing both here would
    quietly shorten how long a live draft's identifier survives.
    """
    row = await insert(
        status="pending", created_at=ago(hours=1), expires_at=datetime.now(UTC) + timedelta(hours=1)
    )

    await sweep_once(settings())

    assert await status_of(row) == "pending"


async def test_stale_send_counters_are_removed() -> None:
    """Resend's quota resets daily, so last week's counts are dead weight."""
    from datetime import date

    from sqlalchemy import text

    from app.db import pool

    stale_day = date.today() - timedelta(days=30)

    # Committed before the sweep runs. `session_scope` commits on the way out of
    # the block, so holding it open across `sweep_once` would leave the INSERT
    # invisible to the sweep's own connection — and the assertion would then be
    # testing transaction visibility rather than the sweep.
    async with pool.session_scope() as session:
        await session.execute(
            text("DELETE FROM send_counters WHERE day = :day"), {"day": stale_day}
        )
        await session.execute(
            text("INSERT INTO send_counters (day, count) VALUES (:day, 1)"), {"day": stale_day}
        )

    result = await sweep_once(settings())

    async with pool.session_scope() as session:
        remaining = (
            await session.execute(
                text("SELECT count(*) FROM send_counters WHERE day = :day"), {"day": stale_day}
            )
        ).scalar_one()

    assert result.old_counters >= 1
    assert remaining == 0


async def test_a_second_sweep_does_nothing_the_first_did_not() -> None:
    """Sweeping is idempotent, which is what makes it safe to trigger on a
    one-in-fifty request rather than on a schedule."""
    await insert(status="pending", created_at=ago(days=30), expires_at=ago(days=1))

    first = await sweep_once(settings())
    second = await sweep_once(settings())

    assert second.total == 0, f"first removed {first}, second removed {second}"


async def test_a_held_lock_skips_the_sweep_rather_than_waiting() -> None:
    """Waiting would put a DELETE on the request path.

    The lock is **transaction-scoped** (`pg_try_advisory_xact_lock`), which is
    the only form that survives PgBouncer transaction pooling on the pooled Neon
    URL. A session-level `pg_try_advisory_lock` can be taken on one backend and
    unlocked on another, leaving it held forever — after which every sweep
    silently no-ops and retention stops working.

    Holding it from a second connection is exactly the contention this guards.
    The holder's transaction stays open, so its lock stays held.
    """
    from sqlalchemy import text

    from app.core.retention import SWEEP_LOCK_ID
    from app.db import pool

    # Held open across the sweep, on purpose. `session_scope` commits on exit,
    # which would release a transaction-scoped lock before the sweep ever
    # looked for it, and the test would pass for the wrong reason.
    async with pool.get_engine().connect() as holder:
        transaction = await holder.begin()
        acquired = (
            await holder.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": SWEEP_LOCK_ID}
            )
        ).scalar_one()
        assert acquired, "could not take the lock to test against"

        result = await sweep_once(settings())

        await transaction.rollback()

    assert result.total == 0


async def test_the_lock_is_released_after_a_sweep() -> None:
    """The bug this pins: a lock that outlives its sweep disables all future ones.

    With the session-level form on a pooled connection, an explicit unlock could
    land on a different backend and the lock would never be freed. With the
    transaction-scoped form, committing releases it — so a second sweep must be
    able to take it.
    """
    from sqlalchemy import text

    from app.core.retention import SWEEP_LOCK_ID
    from app.db import pool

    await sweep_once(settings())

    async with pool.session_scope() as session:
        second_take = (
            await session.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": SWEEP_LOCK_ID}
            )
        ).scalar_one()

    assert second_take is True, "the previous sweep leaked its lock"


async def test_a_dry_run_reports_without_deleting() -> None:
    """The manual escape hatch has to be safe to point at production."""
    from app.core.retention import dry_run

    row = await insert(status="pending", created_at=ago(days=30), expires_at=ago(days=1))

    result = await dry_run()

    assert result.expired_drafts >= 1
    assert await status_of(row) == "pending", "a dry run must not delete"


def settings(**overrides):
    from app.core.config import get_settings

    config = get_settings()
    config.draft_retention_days = overrides.get("draft_retention_days", 7)
    config.sent_row_retention_days = overrides.get("sent_row_retention_days", 30)
    return config


def test_the_sweep_reports_counts_rather_than_rows() -> None:
    """The summary is logged, so it must not be able to carry a message body."""
    from app.core.retention import SweepResult

    rendered = str(SweepResult())

    assert "expired=" in rendered
    assert "@" not in rendered
