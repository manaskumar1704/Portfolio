"""Atomic database transitions for messages.

Two statements, both of which exist to make a race impossible rather than
unlikely.

## `claim_pending`

```sql
UPDATE messages SET status = 'sending' WHERE id = :id AND status = 'pending' RETURNING id
```

The `AND status = 'pending'` is the whole point. Two concurrent requests both
evaluate the WHERE clause, and the row lock means exactly one of them sees
`pending` still true. The loser updates zero rows and gets `None`.

Checking the status first and then updating is the version that breaks: both
requests read `pending`, both update, both send. The window between the two
statements is small and it is still a window.

`sending` is an intermediate state rather than going straight to `sent`, because
the provider call sits between the two. Without it, a crash during the send
would leave the row as `sending` forever with no way to tell whether the mail
went out — which is the one question that matters if a visitor disputes it.

`reap_stale_sends` resolves that: a `sending` row older than its expiry is
assumed failed and becomes `failed`, since a send that never completed cannot be
retried safely either.

## `reserve_daily_send`

```sql
INSERT INTO send_counters (day, count) VALUES (:day, 1)
ON CONFLICT (day) DO UPDATE SET count = send_counters.count + 1
WHERE send_counters.count < :cap
RETURNING count
```

The `WHERE` inside `DO UPDATE` is what makes this a cap rather than a counter.
When the row is at the cap, the update matches nothing, no row is returned, and
the caller refuses. No read-then-write, no transaction, no lock.

This is in the database rather than in process because an in-process counter
resets on every Render spin-down: ten sends before a sleep and ten after would
be twenty.
"""

from sqlalchemy import text

from app.core.logging import get_logger
from app.db import pool

log = get_logger(__name__)


async def claim_pending(message_id: int) -> dict | None:
    """Move a pending draft to `sending`. None means somebody else got it.

    Returns the row the update touched, or None. A None is not an error the
    caller should distinguish between "already sent" and "does not exist" — the
    route reports both as 409/403 identically.
    """
    async with pool.session_scope() as session:
        row = (
            await session.execute(
                text(
                    """
                    UPDATE messages
                    SET status = 'sending'
                    WHERE id = :id AND status = 'pending'
                    RETURNING id, name, email, body, ip_hash
                    """
                ),
                {"id": message_id},
            )
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row.id,
        "name": row.name,
        "email": row.email,
        "body": row.body,
        "ip_hash": row.ip_hash,
    }


async def mark_sent(message_id: int, provider_id: str) -> None:
    """Record a successful send and clear the visitor's IP hash.

    The hash is nulled here rather than by a sweep, because the moment it has
    served its purpose is exactly this moment. Sweeping later would leave a
    window where a sent message still carries an identifier traceable to a person.
    """
    async with pool.session_scope() as session:
        await session.execute(
            text(
                """
                UPDATE messages
                SET status = 'sent', sent_at = now(), provider_id = :provider_id,
                    ip_hash = NULL, origin_ip = NULL
                WHERE id = :id
                """
            ),
            {"id": message_id, "provider_id": provider_id},
        )


async def mark_failed(message_id: int, reason: str) -> None:
    """Record a failed send.

    The reason is a fixed vocabulary, never a provider error string: Resend
    echoes submitted fields back on a validation failure, and a visitor's message
    would end up in this column.
    """
    async with pool.session_scope() as session:
        await session.execute(
            text("UPDATE messages SET status = 'failed' WHERE id = :id"),
            {"id": message_id},
        )
    log.info("message send failed", extra={"message_id": message_id, "reason": reason})


async def mark_expired(message_id: int) -> None:
    async with pool.session_scope() as session:
        await session.execute(
            text("UPDATE messages SET status = 'expired' WHERE id = :id AND status = 'pending'"),
            {"id": message_id},
        )


async def release_daily_send() -> None:
    """Give back a reservation after a failed send.

    Without this, a provider outage would consume the whole daily budget in
    minutes of failed attempts, and the owner would receive nothing for the rest
    of the day.
    """
    async with pool.session_scope() as session:
        await session.execute(
            text(
                """
                UPDATE send_counters SET count = GREATEST(count - 1, 0)
                WHERE day = current_date
                """
            )
        )


async def reserve_daily_send(cap: int) -> int | None:
    """Claim one send from today's budget. None means the cap is reached.

    Atomic: the increment and the cap check are the same statement, so two
    concurrent requests cannot both take the last slot.
    """
    async with pool.session_scope() as session:
        count = (
            await session.execute(
                text(
                    """
                    INSERT INTO send_counters (day, count) VALUES (current_date, 1)
                    ON CONFLICT (day) DO UPDATE SET count = send_counters.count + 1
                    WHERE send_counters.count < :cap
                    RETURNING count
                    """
                ),
                {"cap": cap},
            )
        ).scalar_one_or_none()

    return count


async def reap_stale_sends() -> int:
    """Resolve `sending` rows that outlived their expiry.

    A crash between claiming and marking leaves a row as `sending`, and nothing
    else ever transitions it. A send that never completed cannot be retried
    safely either — the provider may have accepted it — so `failed` is the honest
    terminal state, and it is visible to the owner rather than silent.
    """
    async with pool.session_scope() as session:
        result = await session.execute(
            text(
                """
                UPDATE messages SET status = 'failed'
                WHERE status = 'sending' AND expires_at < now()
                """
            )
        )

    reaped = result.rowcount or 0
    if reaped:
        log.info("reaped stale sends", extra={"count": reaped})
    return reaped


async def get_draft(message_id: int) -> dict | None:
    """Fetch a draft for display. No token, by design."""
    async with pool.session_scope() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT id, name, email, body, status, created_at, expires_at
                    FROM messages WHERE id = :id
                    """
                ),
                {"id": message_id},
            )
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row.id,
        "name": row.name,
        "email": row.email,
        "body": row.body,
        "status": row.status,
        "created_at": row.created_at,
        "expires_at": row.expires_at,
    }
