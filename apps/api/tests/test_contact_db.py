"""Contact: the database half. Integration tests against real Postgres.

What is worth checking here is what `create_draft` writes, because that is the
foundation phase 6's approval route stands on. The route's own refusal matrix —
wrong token, wrong id, wrong IP, expired, replayed — is tested in
`test_send_route.py`; this file owns the row facts:

- no plaintext address is ever stored (`origin_ip` stays NULL);
- the binding is a salted `ip_hash`, hashed from the request context, which the
  registry cannot influence (`registry.call` passes handlers model arguments
  only, so an IP parameter would be whatever the model typed);
- the fail-closed path: with no usable salt, a draft that could never be
  approved is refused rather than created.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.client_ip import current_client_ip
from app.core.config import get_settings
from app.db import pool
from app.services import contact
from tests.helpers import DEFAULT_SALT, pending_ip_hash

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not get_settings().database_url, reason="DATABASE_URL not set"),
]

IP = "203.0.113.10"
OTHER_IP = "198.51.100.7"


@pytest.fixture(autouse=True)
async def clean_table(ready_db):
    """The module owns the table while it runs: empty in, empty out.

    A teardown wipe means a test cannot forget to delete the row it made, which
    is the bug the old per-test cleanup had to be remembered against.
    """
    await _wipe()
    yield
    await _wipe()


@pytest.fixture
def with_salt(monkeypatch) -> None:
    """Pin the salt so the digests below do not depend on a developer's .env."""
    monkeypatch.setattr(get_settings(), "ip_hash_salt", DEFAULT_SALT)


async def _wipe() -> None:
    async with pool.session_scope() as session:
        await session.execute(text("DELETE FROM messages"))


async def _create_bound() -> contact.Draft:
    """Bind the request context IP and create one draft (salt pinned by the test)."""
    current_client_ip.set(IP)
    return await contact.create_draft("Ada Lovelace", "ada@example.com", "Hello")


# --- What the service writes -------------------------------------------------


async def test_a_draft_is_stored_pending(ready_db, with_salt) -> None:
    draft = await _create_bound()

    assert draft.id > 0
    assert draft.token

    async with pool.session_scope() as session:
        row = (
            await session.execute(
                text("SELECT status, email, expires_at FROM messages WHERE id = :id"),
                {"id": draft.id},
            )
        ).fetchone()

    assert row.status == "pending"
    assert row.email == "ada@example.com"
    assert row.expires_at > datetime.now(UTC)


async def test_no_plaintext_address_is_stored(ready_db, with_salt) -> None:
    """`origin_ip` is nullable since c3d4e5f6a7b8 and the service stopped writing it.

    The send route's `_ip_matches` compares salted digests only, so the plaintext
    form is not needed by anything and would be a PII column nobody reads.
    """
    draft = await _create_bound()

    async with pool.session_scope() as session:
        origin_ip = (
            await session.execute(
                text("SELECT origin_ip FROM messages WHERE id = :id"), {"id": draft.id}
            )
        ).scalar_one()

    assert origin_ip is None


async def test_the_row_is_bound_to_the_request_ip(ready_db, with_salt) -> None:
    """The binding the whole approval path stands on.

    Checked through the route's own seam (`_ip_matches`): the address the request
    resolved matches, a different address does not, and the legacy unbound form
    (`ip_hash IS NULL`) fails closed. That last one is why the service refuses to
    create rows without a hash rather than writing one.
    """
    from app.api.messages import _ip_matches

    draft = await _create_bound()

    async with pool.session_scope() as session:
        ip_hash = (
            await session.execute(
                text("SELECT ip_hash FROM messages WHERE id = :id"), {"id": draft.id}
            )
        ).scalar_one()

    assert ip_hash == pending_ip_hash(IP, DEFAULT_SALT)
    assert _ip_matches(ip_hash, IP, get_settings())
    assert not _ip_matches(ip_hash, OTHER_IP, get_settings())
    assert not _ip_matches(None, IP, get_settings())


async def test_without_a_usable_salt_the_draft_is_refused(ready_db, monkeypatch) -> None:
    """Fail closed: an unbound row is a message the visitor can never approve."""
    monkeypatch.setattr(get_settings(), "ip_hash_salt", "")
    current_client_ip.set(IP)

    with pytest.raises(contact.DraftError):
        await contact.create_draft("Ada", "ada@example.com", "Hello")


async def test_the_tool_path_binds_the_request_context(ready_db, with_salt) -> None:
    """The registry passes the handler nothing but model arguments.

    If the IP travelled as a tool argument it would be something the model typed,
    and the model talking to a prompt-injected visitor could bind any address it
    wanted. Prove that the context set by the request handler is what lands in
    the column.
    """
    from app.tools import registry

    current_client_ip.set(IP)
    try:
        result, error = await registry.call(
            "draft_message",
            {"name": "Ada", "email": "ada@example.com", "body": "Hello"},
        )
    finally:
        current_client_ip.set("")

    assert error is None
    assert result["sent"] is False

    async with pool.session_scope() as session:
        row = (
            await session.execute(
                text("SELECT ip_hash, origin_ip FROM messages WHERE id = :id"),
                {"id": result["draft_id"]},
            )
        ).fetchone()

    assert row.ip_hash == pending_ip_hash(IP, DEFAULT_SALT)
    assert row.origin_ip is None


async def test_the_stored_token_is_a_hash_not_the_token(ready_db, with_salt) -> None:
    """A leaked messages row must not be replayable into sending mail."""
    draft = await _create_bound()

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


async def test_the_email_is_normalised_on_the_way_in(ready_db, with_salt) -> None:
    current_client_ip.set(IP)
    await contact.create_draft("Ada", "Ada Lovelace <Ada@Example.com>", "Hello")

    async with pool.session_scope() as session:
        stored = (await session.execute(text("SELECT email FROM messages"))).scalar_one()

    assert stored == "ada@example.com"


# --- Properties a fresh row has ----------------------------------------------


async def test_a_draft_expires_in_the_future(ready_db, with_salt) -> None:
    draft = await _create_bound()

    assert draft.expires_at > datetime.now(UTC)
    delta = draft.expires_at - draft.created_at
    assert timedelta(hours=71) < delta <= timedelta(hours=73)


# --- Constraints -------------------------------------------------------------


async def test_the_database_refuses_an_unknown_status(ready_db) -> None:
    """Free text here would make a typo in phase 6 look like a pending draft.

    Postgres rejects the value when it casts to the enum, before any constraint is
    checked, so this surfaces as a DBAPIError subclass rather than the
    IntegrityError a CHECK constraint would raise. All three are accepted because
    the point is that the write is refused, not which layer refuses it.
    """
    from sqlalchemy.exc import DBAPIError

    with pytest.raises((DBAPIError, IntegrityError)):
        async with pool.session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status, approval_token_hash,
                                          ip_hash, expires_at)
                    VALUES ('a', 'a@b.com', 'hi', 'confimed', :h, :h, now() + interval '1 hour')
                    """
                ),
                {"h": "0" * 64},
            )


async def test_expires_at_is_required(ready_db) -> None:
    """A NULL here would read as 'never expires' to every query."""

    with pytest.raises(IntegrityError):
        async with pool.session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status, approval_token_hash)
                    VALUES ('a', 'a@b.com', 'hi', 'pending', :h)
                    """
                ),
                {"h": "0" * 64},
            )


async def test_every_documented_status_is_accepted(ready_db) -> None:
    """The enum has to hold every value phase 6 will write."""

    for status in ("pending", "expired", "failed"):
        async with pool.session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status, approval_token_hash,
                                          ip_hash, expires_at)
                    VALUES ('a', 'a@b.com', 'hi', :s, :h, :h, now() + interval '1 hour')
                    """
                ),
                {"s": status, "h": "0" * 64},
            )

    async with pool.session_scope() as session:
        count = (await session.execute(text("SELECT count(*) FROM messages"))).scalar_one()

    assert count == 3
