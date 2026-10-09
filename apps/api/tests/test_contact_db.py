"""Contact: the database half. Integration tests against real Postgres.

What is worth checking here is the row and the lookup, because both are the
foundation phase 6's approval route stands on.

The critical property is that a draft cannot be approved without the token *and*
the originating IP. `get_draft_for_approval` returns None for all three of: wrong
id, wrong token, wrong IP, expired, already sent. Testing only the happy path
would leave the actual security boundary unverified.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db import pool
from app.services import contact

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not get_settings().database_url, reason="DATABASE_URL not set"),
]

IP = "203.0.113.10"


@pytest.fixture
async def ready_db():
    await pool.setup(get_settings())
    try:
        yield pool
    finally:
        await pool.teardown()


async def wipe() -> None:
    async with pool.session_scope() as session:
        await session.execute(text("DELETE FROM messages"))


async def test_a_draft_is_stored_pending(ready_db) -> None:
    await wipe()

    draft = await contact.create_draft("Ada Lovelace", "ada@example.com", "Hello", IP)

    assert draft.id > 0
    assert draft.token

    async with pool.session_scope() as session:
        row = (
            await session.execute(
                text("SELECT status, email, origin_ip, expires_at FROM messages WHERE id = :id"),
                {"id": draft.id},
            )
        ).fetchone()

    assert row.status == "pending"
    assert row.email == "ada@example.com"
    assert row.origin_ip == IP


async def test_the_stored_token_is_a_hash_not_the_token(ready_db) -> None:
    """A leaked messages row must not be replayable into sending mail."""
    await wipe()

    draft = await contact.create_draft("Ada", "ada@example.com", "Hello", IP)

    async with pool.session_scope() as session:
        stored = (
            await session.execute(
                text("SELECT approval_token_hash FROM messages WHERE id = :id"),
                {"id": draft.id},
            )
        ).scalar_one()

    assert stored == contact.hash_token(draft.token)
    assert stored != draft.token
    assert draft.token not in stored


async def test_the_email_is_normalised_on_the_way_in(ready_db) -> None:
    await wipe()

    await contact.create_draft("Ada", "Ada Lovelace <Ada@Example.com>", "Hello", IP)

    async with pool.session_scope() as session:
        stored = (await session.execute(text("SELECT email FROM messages"))).scalar_one()

    assert stored == "ada@example.com"


async def test_a_draft_expires_in_the_future(ready_db) -> None:
    await wipe()

    draft = await contact.create_draft("Ada", "ada@example.com", "Hello", IP)

    assert draft.expires_at > datetime.now(UTC)
    delta = draft.expires_at - draft.created_at
    assert timedelta(hours=71) < delta <= timedelta(hours=73)


# --- The approval lookup ----------------------------------------------------


async def test_the_right_token_and_ip_approves(ready_db) -> None:
    """The happy path phase 6 depends on."""
    await wipe()

    draft = await contact.create_draft("Ada", "ada@example.com", "Hello", IP)

    found = await contact.get_draft_for_approval(draft.id, draft.token, IP)

    assert found is not None
    assert found.id == draft.id
    assert found.email == "ada@example.com"


async def test_a_wrong_token_does_not_approve(ready_db) -> None:
    await wipe()

    draft = await contact.create_draft("Ada", "ada@example.com", "Hello", IP)

    assert await contact.get_draft_for_approval(draft.id, "wrong", IP) is None


async def test_a_right_token_from_another_ip_does_not_approve(ready_db) -> None:
    """The binding that stops a leaked link from being useful elsewhere."""
    await wipe()

    draft = await contact.create_draft("Ada", "ada@example.com", "Hello", IP)

    assert await contact.get_draft_for_approval(draft.id, draft.token, "198.51.100.7") is None


async def test_a_wrong_id_does_not_approve(ready_db) -> None:
    await wipe()

    draft = await contact.create_draft("Ada", "ada@example.com", "Hello", IP)

    assert await contact.get_draft_for_approval(draft.id + 999, draft.token, IP) is None


async def test_an_expired_draft_does_not_approve(ready_db) -> None:
    """A token issued today must not still work next year."""
    await wipe()

    draft = await contact.create_draft("Ada", "ada@example.com", "Hello", IP)
    async with pool.session_scope() as session:
        await session.execute(
            text("UPDATE messages SET expires_at = now() - interval '1 hour' WHERE id = :id"),
            {"id": draft.id},
        )

    assert await contact.get_draft_for_approval(draft.id, draft.token, IP) is None


async def test_an_already_sent_draft_does_not_approve_twice(ready_db) -> None:
    """Idempotence. Double-sending on a double-click is a real failure."""
    await wipe()

    draft = await contact.create_draft("Ada", "ada@example.com", "Hello", IP)
    async with pool.session_scope() as session:
        await session.execute(
            text("UPDATE messages SET status = 'sent', sent_at = now() WHERE id = :id"),
            {"id": draft.id},
        )

    assert await contact.get_draft_for_approval(draft.id, draft.token, IP) is None


async def test_the_lookup_never_returns_the_token(ready_db) -> None:
    """The approval route needs the row, not the capability."""
    await wipe()

    draft = await contact.create_draft("Ada", "ada@example.com", "Hello", IP)
    found = await contact.get_draft_for_approval(draft.id, draft.token, IP)

    assert found is not None
    assert found.token == ""


# --- Constraints ------------------------------------------------------------


async def test_the_database_refuses_an_unknown_status(ready_db) -> None:
    """Free text here would make a typo in phase 6 look like a pending draft.

    Postgres rejects the value when it casts to the enum, before any constraint is
    checked, so this surfaces as a DBAPIError subclass rather than the
    IntegrityError a CHECK constraint would raise. All three are accepted because
    the point is that the write is refused, not which layer refuses it.
    """
    from sqlalchemy.exc import DBAPIError

    await wipe()

    with pytest.raises((DBAPIError, IntegrityError)):
        async with pool.session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status, approval_token_hash,
                                          origin_ip, expires_at)
                    VALUES ('a', 'a@b.com', 'hi', 'confimed', :h, :ip, now() + interval '1 hour')
                    """
                ),
                {"h": "0" * 64, "ip": IP},
            )


async def test_expires_at_is_required(ready_db) -> None:
    """A NULL here would read as 'never expires' to every query."""
    await wipe()

    with pytest.raises(IntegrityError):
        async with pool.session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status, approval_token_hash, origin_ip)
                    VALUES ('a', 'a@b.com', 'hi', 'pending', :h, :ip)
                    """
                ),
                {"h": "0" * 64, "ip": IP},
            )


async def test_every_documented_status_is_accepted(ready_db) -> None:
    """The enum has to hold every value phase 6 will write."""
    await wipe()

    for status in ("pending", "expired", "failed"):
        async with pool.session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status, approval_token_hash,
                                          origin_ip, expires_at)
                    VALUES ('a', 'a@b.com', 'hi', :s, :h, :ip, now() + interval '1 hour')
                    """
                ),
                {"s": status, "h": "0" * 64, "ip": IP},
            )

    async with pool.session_scope() as session:
        count = (await session.execute(text("SELECT count(*) FROM messages"))).scalar_one()

    assert count == 3
