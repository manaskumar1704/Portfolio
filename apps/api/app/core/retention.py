"""Retention: what to delete, and when anything decides to do it.

## There is no cron on this tier

Render free has no scheduled jobs, Neon's free tier has no cron extension
enabled, and GitHub Actions disables scheduled workflows on public repositories
after 60 days of repository inactivity — so a keep-alive cron that silently stops
is worse than no cron, because it looks identical to a working one.

Two triggers remain, both free:

1. **Container boot.** Render starts the container; the sweep runs once. This is
   the reliable one.
2. **Opportunistically on `/chat`.** One request in fifty, guarded by a Postgres
   advisory lock so only one process sweeps even with several running. `/chat`
   already opens a database connection, so the marginal cost is one indexed
   DELETE on a table that is nearly always empty.

The honest consequence, recorded rather than papered over: **when a site has no
traffic, nothing sweeps.** Stale drafts persist until the next visitor. They are
inert rows holding a salted digest rather than a readable address, so the risk is
bounded — but this is retention-by-laziness, not retention-by-policy.

`uv run python -m app.core.retention` is the manual escape hatch, and a Neon cron
or an authenticated external sweep endpoint would close the gap properly.

## What gets deleted, and what does not

| Row | Age | Action |
|---|---|---|
| `pending` | past `expires_at` | **deleted** |
| `pending` | past `draft_retention_days` | **deleted**, whatever the expiry says |
| `sent` / `failed` | past `sent_row_retention_days` | **deleted** |
| any, still holding `ip_hash` | immediately on send | `ip_hash` nulled, row kept |

The row survives a send on purpose. Clearing the hash is about privacy; deleting
the row is about tidiness, and a visitor disputing that their message was sent is
a real enough possibility that the record should outlive the identifier in it.
"""

import asyncio
import random

from sqlalchemy import text

from app.core.config import Settings
from app.core.logging import get_logger
from app.db import pool

log = get_logger(__name__)

# Postgres advisory lock key. Arbitrary but fixed: two processes running the
# sweep at once is harmless (the DELETEs are idempotent) and serialising them
# avoids doing the work twice on a busy site.
SWEEP_LOCK_ID = 4_720_011


class SweepResult:
    """What one sweep did. Every field is a count, so logging is safe."""

    def __init__(self) -> None:
        self.expired_drafts = 0
        self.stale_drafts = 0
        self.old_sent = 0
        self.old_counters = 0
        self.reaped_sends = 0

    @property
    def total(self) -> int:
        return (
            self.expired_drafts
            + self.stale_drafts
            + self.old_sent
            + self.old_counters
            + self.reaped_sends
        )

    def __str__(self) -> str:
        return (
            f"expired={self.expired_drafts} stale={self.stale_drafts} "
            f"sent={self.old_sent} counters={self.old_counters} "
            f"reaped={self.reaped_sends}"
        )


async def sweep_once(settings: Settings) -> SweepResult:
    """Run one sweep under an advisory lock. Returns zeroes if another got it."""
    from app.db.queries.messages import reap_stale_sends

    result = SweepResult()

    async with pool.session_scope() as session:
        # `pg_try_advisory_xact_lock`, NOT `pg_try_advisory_lock`.
        #
        # The sweep runs on `pool.session_scope()`, which is built from
        # `DATABASE_URL` — the POOLED Neon URL, i.e. PgBouncer in transaction
        # pooling mode. Session-level advisory locks do not survive that: the lock
        # is taken on whichever backend served this transaction, and the matching
        # unlock can be routed to a different one, leaving the lock held forever.
        # Every later sweep would then report "another process holds the lock" and
        # retention would quietly stop working, with nothing in the logs but a
        # debug line nobody reads.
        #
        # The `_xact_` variant is released by COMMIT or ROLLBACK, which
        # `session_scope` guarantees, so the lock cannot outlive its transaction
        # whichever backend served it.
        #
        # `try_` rather than the blocking form: waiting would put a DELETE on the
        # request path.
        acquired = (
            await session.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": SWEEP_LOCK_ID}
            )
        ).scalar_one()

        if not acquired:
            log.debug("sweep skipped: another process holds the lock")
            return result

        # Expired and unsent. The condition is `expires_at` rather than a
        # separate age column: the expiry is already the answer, and a second
        # column would be a second thing to keep correct.
        result.expired_drafts = (
            await session.execute(
                text(
                    """
                    DELETE FROM messages
                    WHERE status IN ('pending', 'sending') AND expires_at < now()
                    """
                )
            )
        ).rowcount

        # Unsent but unexpired, and past the retention window anyway. A draft
        # can be written with an expiry the visitor will never reach, and this
        # is the backstop.
        result.stale_drafts = (
            await session.execute(
                text(
                    """
                    DELETE FROM messages
                    WHERE status = 'pending'
                      AND created_at < now() - make_interval(days => :days)
                    """
                ),
                {"days": settings.draft_retention_days},
            )
        ).rowcount

        # Sent and failed rows keep their body for a while, then go. The IP
        # hash was already cleared at send time.
        result.old_sent = (
            await session.execute(
                text(
                    """
                    DELETE FROM messages
                    WHERE status IN ('sent', 'failed')
                      AND COALESCE(sent_at, created_at)
                          < now() - make_interval(days => :days)
                    """
                ),
                {"days": settings.sent_row_retention_days},
            )
        ).rowcount

        # Counter rows older than a week are dead weight. Resend's quota
        # resets daily, so yesterday's count is worth nothing.
        result.old_counters = (
            await session.execute(text("DELETE FROM send_counters WHERE day < current_date - 7"))
        ).rowcount

        # No unlock. The lock is transaction-scoped and `session_scope` commits
        # on the way out of this block, which releases it. An explicit unlock here
        # would be the session-level mistake this block exists to fix.

    result.reaped_sends = await reap_stale_sends()

    if result.total:
        log.info("retention sweep", extra={"detail": str(result)})

    return result


async def sweep_on_boot(settings: Settings) -> None:
    """Run once at startup, swallowing failures.

    A retention problem must not stop the app from serving `/health`. A site that
    refuses traffic because a DELETE failed is a worse outcome than one with
    stale rows.

    **Does not manage the pool.** The caller (`app.main`'s lifespan) has already
    built the engine, and this used to call `pool.teardown()` on its way out —
    which disposed the live pool, so the first real request after boot found no
    session factory. Every caller here already has a working pool; this function
    only borrows it.
    """
    try:
        await sweep_once(settings)
    except Exception as exc:
        log.warning("boot retention sweep failed: %s", type(exc).__name__)


async def maybe_sweep(settings: Settings) -> None:
    """Run the sweep occasionally. The trigger for a site with no traffic.

    Probabilistic rather than on a timer because there is no timer. One in fifty
    chat requests is frequent enough on a busy site and rare enough on a quiet one
    that it is invisible.
    """
    if settings.retention_sweep_percent <= 0:
        return
    if random.randint(1, 100) > settings.retention_sweep_percent:
        return

    try:
        await sweep_once(settings)
    except Exception as exc:
        log.warning("opportunistic sweep failed: %s", type(exc).__name__)


async def dry_run(settings: Settings | None = None) -> SweepResult:
    """What a sweep would remove, without removing it.

    Not a parameter on `sweep_once`: a boolean that means "do the destructive
    thing" is a flag someone will eventually get wrong.

    Borrows the pool rather than building it, for the same reason `sweep_on_boot`
    does. Managing the engine here disposed the live pool out from under the
    caller, which is invisible in the CLI and fatal in a test.
    """
    from app.core.config import get_settings

    settings = settings or get_settings()
    result = SweepResult()

    # The same four predicates as `sweep_once`, as counts. A `SELECT count(*)`
    # for a table that is nearly always empty is cheap, and the point of a dry run
    # is that nothing here can delete anything by accident.
    queries = {
        "expired_drafts": (
            "SELECT count(*) FROM messages "
            "WHERE status IN ('pending', 'sending') AND expires_at < now()",
            {},
        ),
        "stale_drafts": (
            "SELECT count(*) FROM messages WHERE status = 'pending' "
            "AND created_at < now() - make_interval(days => :days)",
            {"days": settings.draft_retention_days},
        ),
        "old_sent": (
            "SELECT count(*) FROM messages WHERE status IN ('sent', 'failed') "
            "AND COALESCE(sent_at, created_at) < now() - make_interval(days => :days)",
            {"days": settings.sent_row_retention_days},
        ),
        "old_counters": (
            "SELECT count(*) FROM send_counters WHERE day < current_date - 7",
            {},
        ),
    }

    async with pool.session_scope() as session:
        for attribute, (query, params) in queries.items():
            setattr(result, attribute, (await session.execute(text(query), params)).scalar_one())

    return result


def main() -> int:
    """`uv run python -m app.core.retention --dry-run`"""
    import argparse

    parser = argparse.ArgumentParser(description="Delete stale messages and counters.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be removed without removing it.",
    )
    args = parser.parse_args()

    from app.core.config import get_settings
    from app.core.logging import configure_logging

    settings = get_settings()
    configure_logging(settings.log_level)

    # The one place that owns the pool's whole lifecycle. Inside the app the
    # lifespan does; in the CLI nothing else will, so it does here.
    async def run() -> SweepResult:
        await pool.setup(settings)
        try:
            return await (dry_run(settings) if args.dry_run else sweep_once(settings))
        finally:
            await pool.teardown()

    verb = "would remove" if args.dry_run else "removed"
    print(f"{verb}: {asyncio.run(run())}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
