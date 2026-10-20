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
                    RETURNING id, name, email, body, company, role, subject
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
        # The form's context fields. They ride to `build_notification`, which
        # spells them into the owner's email; chat-created drafts carry none.
        "company": row.company,
        "role": row.role,
        "subject": row.subject,
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


async def update_pending_body(message_id: int, body: str) -> dict | None:
    """Rewrite a pending draft's body after authorisation. None when not pending.

    Same `AND status = 'pending'` guard as `claim_pending`: the claim for send or
    the cancel for withdrawal and this edit are all racing on one row, and the
    row lock picks exactly one winner per state change.

    The token is not rotated on edit. The edit is authorised BY the token; the
    token already lives in a browser, and rotating would make the happy path
    (edit then approve from the same page) impossible.
    """
    async with pool.session_scope() as session:
        row = (
            await session.execute(
                text(
                    """
                    UPDATE messages
                    SET body = :body
                    WHERE id = :id AND status = 'pending'
                    RETURNING id, name, email, body, status, created_at, expires_at
                    """
                ),
                {"id": message_id, "body": body},
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


async def cancel_pending(message_id: int) -> bool:
    """Withdraw a pending draft: status becomes `cancelled`, the hash goes to null.

    The IP hash is cleared here rather than left to a sweep, same as in
    `mark_sent`: the binding between draft and connection has served its purpose
    the moment the draft can never be approved again, which is now. The row
    itself survives for the retention window, because "did my withdrawal
    register?" is a dispute worth being able to answer.
    """
    async with pool.session_scope() as session:
        result = await session.execute(
            text(
                """
                UPDATE messages
                SET status = 'cancelled', ip_hash = NULL
                WHERE id = :id AND status = 'pending'
                """
            ),
            {"id": message_id},
        )

    return bool(result.rowcount)


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
