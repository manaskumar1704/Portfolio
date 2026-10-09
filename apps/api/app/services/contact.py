"""Visitor messages. Phase 5 writes them; only phase 6 sends them.

## What this module does and does not do

`create_draft` writes a `pending` row and returns a token to the visitor's
browser. That is the end of it. There is no Resend call, no SMTP, no outbound
network of any kind in this file, and that is deliberate rather than pending work
waiting on a credential — the send path is a separate HTTP route with its own
authentication, not a tool.

The reason is the threat model. `draft_message` is reachable by anyone who loads
the page, and a tool the model can call is a tool a prompt-injected visitor can
trigger. If sending were one more leg of that chain, the injection path and the
send path would be the same path. They are not.

## The token

`approval_token` is 32 bytes from `secrets.token_urlsafe`, and only its SHA-256
goes in the database. A leaked `messages` row must not be replayable into sending
mail on the owner's behalf.

The plaintext token exists in exactly two places: the response body that goes to
the visitor's browser, and the confirmation event on the SSE stream. It is never
written to a log line, never put in a prompt, and never returned in a tool
result — if the model could read it, the model could talk a visitor into
approving their own draft.

`# ponytail: origin IP checked with simple inequality. Move to a subnet-aware
match when there is a reverse proxy in front that rewrites the client address.`

## Sanitization

The body is a stranger's text that will be emailed to the owner. It is stored
verbatim minus control characters, because mangling someone's message before they
approve it is worse than storing it. The HTML email in phase 6 is the place where
escaping actually matters, and that is where it happens.
"""

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parseaddr

from sqlalchemy import text

from app.core.logging import get_logger
from app.db import pool

log = get_logger(__name__)

TOKEN_BYTES = 32

# How long a draft stays approvable. Long enough for a recruiter to read the
# message and click, short enough that an abandoned draft does not become a
# permanent send capability.
DRAFT_TTL = timedelta(hours=72)

MAX_NAME = 200
MAX_EMAIL = 320
MAX_BODY = 4000

# Control characters, minus tab and newline. A body with \x00 in it is either a
# bug or an attempt to break something downstream.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# An email is either a bare address or `Name <address>`. Anything else is not a
# contact and is rejected rather than sanitised, because guessing at intent here
# means mail to an address nobody chose.
_ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DraftError(ValueError):
    """The draft could not be created. The message is shown to the visitor."""


@dataclass(frozen=True)
class Draft:
    """A saved draft. `token` is plaintext and goes to the browser only."""

    id: int
    name: str
    email: str
    body: str
    created_at: datetime
    expires_at: datetime
    token: str


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 of the token, hex. Stored instead of the token itself."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def clean_text(value: str) -> str:
    """Strip control characters and collapse the edges."""
    return _CONTROL_CHARS.sub("", value or "").strip()


def normalise_email(value: str) -> str:
    """Accept `a@b.com` or `Name <a@b.com>`; return the bare address.

    `parseaddr` is used rather than a regex because it handles the quoting rules
    for display names, which a regex does not. The regex afterwards is the
    actual check: parseaddr is permissive and will happily return `not-an-email`
    with an empty address, which is not something to send mail to.
    """
    value = clean_text(value)
    _, address = parseaddr(value)

    candidate = (address or value).strip().lower()
    if not _ADDRESS.match(candidate):
        raise DraftError("That does not look like a valid email address.")
    if len(candidate) > MAX_EMAIL:
        raise DraftError("That email address is too long.")
    return candidate


def validate_draft(name: str, email: str, body: str) -> tuple[str, str, str]:
    """Validate and clean the three fields. Raises `DraftError` with a message.

    The lengths are enforced here as well as in the Pydantic model because phase
    6's HTTP route will reuse this function, and it should not have to trust that
    a different caller validated first.
    """
    name = clean_text(name)
    if not name:
        raise DraftError("Please include your name.")
    if len(name) > MAX_NAME:
        raise DraftError("That name is too long.")

    address = normalise_email(email)

    body = clean_text(body)
    if not body:
        raise DraftError("The message is empty.")
    if len(body) > MAX_BODY:
        raise DraftError(f"The message is too long (limit {MAX_BODY} characters).")

    return name, address, body


async def create_draft(name: str, email: str, body: str, origin_ip: str) -> Draft:
    """Write a `pending` row. Returns the draft with its plaintext token."""
    name, address, body = validate_draft(name, email, body)

    token = generate_token()
    token_hash = hash_token(token)

    async with pool.session_scope() as session:
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO messages (name, email, body, status,
                                          approval_token_hash, origin_ip, expires_at)
                    VALUES (:name, :email, :body, 'pending', :token_hash, :ip, :expires)
                    RETURNING id, created_at, expires_at
                    """
                ),
                {
                    "name": name,
                    "email": address,
                    "body": body,
                    "token_hash": token_hash,
                    "ip": (origin_ip or "unknown")[:45],
                    "expires": datetime.now(UTC) + DRAFT_TTL,
                },
            )
        ).fetchone()

    draft = Draft(
        id=row.id,
        name=name,
        email=address,
        body=body,
        created_at=row.created_at,
        expires_at=row.expires_at,
        token=token,
    )

    # Logged without the token and without the message body. The token is the
    # send capability; the body is a stranger's words.
    log.info(
        "draft created",
        extra={"message_id": draft.id, "chars": len(body), "expires_at": str(draft.expires_at)},
    )
    return draft


def confirmation_for_model(draft: Draft) -> str:
    """What the model is told after a draft is saved.

    Unambiguous about the message *not* having been sent, because the model is
    the one talking to the visitor and the failure this prevents is a bot saying
    "I've sent your message" when nothing was sent. The token is deliberately
    absent: the model must not be able to read the send capability.
    """
    return (
        f"Saved as draft #{draft.id}, NOT sent. "
        f"Nothing has been emailed yet. "
        f"The visitor now needs to approve it in the chat interface before it is sent. "
        f"Tell them it is saved and waiting for their approval, and do not claim it "
        f"has been sent. If they ask you to send it, explain that they need to use "
        f"the approve button."
    )


async def get_draft_for_approval(message_id: int, token: str, origin_ip: str) -> Draft | None:
    """Look up a draft for approval. None when anything does not line up.

    Three checks, all required, all in one query so a partial match cannot leak
    the difference:

    - the id matches a row
    - the token hash matches (compared in SQL, not in Python, so a timing
      difference cannot distinguish "wrong id" from "wrong token")
    - the originating IP matches
    - the draft has not expired and is still pending

    Phase 6 calls this. It lives here because the row shape, the token hashing and
    the expiry rule are all this module's business.
    """
    async with pool.session_scope() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT id, name, email, body, created_at, expires_at
                    FROM messages
                    WHERE id = :id
                      AND approval_token_hash = :token_hash
                      AND origin_ip = :ip
                      AND status = 'pending'
                      AND expires_at > now()
                    """
                ),
                {
                    "id": message_id,
                    "token_hash": hash_token(token),
                    "ip": origin_ip,
                },
            )
        ).fetchone()

    if row is None:
        return None

    return Draft(
        id=row.id,
        name=row.name,
        email=row.email,
        body=row.body,
        created_at=row.created_at,
        expires_at=row.expires_at,
        token="",  # never re-exposed
    )
