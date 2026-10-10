"""Test helpers for the phase-6 send route.

The send route needs a row that exists with a known token and a known IP. Rather
than duplicating the INSERT in every test, it lives here once.

These helpers do real database work and skip without DATABASE_URL, so they are
integration-shaped even though the tests that use them do not carry the marker.
"""

from dataclasses import dataclass

from app.core.client_ip import hash_ip

from app.db import pool

DEFAULT_SALT = "a-sufficiently-long-test-salt"


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

    return PendingDraft(id=row_id, token=token)


def pending_ip_hash(ip: str, salt: str = DEFAULT_SALT) -> str:
    """The stored form of an address, for cross-checking both sides.

    `hash_ip` normalises internally, so this is simply the hash. The indirection
    exists so a test can assert "the row and the request agree" without knowing
    which normalisation each side applies.
    """
    return hash_ip(ip, salt)
