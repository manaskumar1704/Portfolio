"""POST /messages/{id}/send — the route that actually sends mail.

## The order of checks is the design

    1. body size          a 10 MB body costs nothing to refuse
    2. per-IP rate limit  cheap; stops a flood before anything is looked up
    3. token compare      constant-time, against a stored SHA-256
    4. IP match           normalised, so an IPv6 rotation is not a failure
    5. status, expiry     pending and unexpired
    6. daily cap          the owner's global budget
    7. atomic claim       pending -> sending, exactly one winner
    8. Resend

Steps 2 and 3 are in that order deliberately. Checking the token first means
every guess with a fake token reaches the database, which is a free
denial-of-service on the one endpoint that matters most. The token comparison is
cheap; the rate limiter is cheaper.

Steps 3, 4 and 5 are in that order for a different reason: each is a refusal the
visitor can act on. A rate-limited request should wait. A wrong token cannot be
fixed. A mobile network change cannot be fixed either, but it can be explained.

## Three refusals, one message

A wrong token, a wrong IP, and an unknown message id all return 403 with the
**same** message. Distinguishing them turns the route into an oracle: a 403 that
said "wrong IP, but the draft exists" confirms an id an attacker guessed.

The message names the likely cause, because a visitor who switched from wifi to
mobile deserves to be told that rather than left staring at a bare refusal. It
does not confirm that a draft exists.

## Replay

Step 7 is one statement, `UPDATE ... WHERE id = :id AND status = 'pending'`. Two
concurrent requests both evaluate the WHERE; the row lock means exactly one sees
`pending` and the other updates zero rows. A double-click, a browser retry and an
attacker replaying a captured token all land on the same 409.

Checking the status first and then updating is the version that breaks: both
requests read `pending`, both update, both send.

## Nothing here logs a token

Not in the access log, not in an error, not in a response body. The token is a
capability and the only place it is ever readable is the browser that received it
in the `draft` event.
"""

import hmac

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.client_ip import client_ip, hash_from_settings
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.ratelimit import RateLimiter
from app.db import pool
from app.db.queries import messages as message_queries
from app.schemas.message import DraftSummary, SendMessageRequest, SendMessageResponse
from app.services import contact
from app.services.email import EmailError, build_notification, send_notification

router = APIRouter(tags=["messages"])
log = get_logger(__name__)

# Separate from the chat limiter: approving is rarer and more consequential than
# asking a question, so it gets its own budget and its own key space.
#
# `per_hour` is passed explicitly because the setting is named in hours. Reading
# `rate_limit_per_minute` here instead is how `approve_limit_per_hour` became a
# setting that existed and did nothing.
_approvals = RateLimiter(
    per_hour=get_settings().approve_limit_per_hour,
    burst=get_settings().approve_limit_per_hour,
)

# A body larger than this is refused before it is parsed. Pydantic would reject
# the fields eventually; this refuses it for free.
MAX_BODY_BYTES = 4096

# One message, three refusal reasons. See the module docstring.
FORBIDDEN = (
    "That request could not be approved. This usually means the connection "
    "changed — you may have switched from wifi to mobile data since writing the "
    "message. Please start a new message from this device."
)


@router.post("/messages/{message_id}/send", response_model=SendMessageResponse)
async def send_message(
    message_id: int,
    request: Request,
    payload: SendMessageRequest,
    response: Response,
) -> SendMessageResponse:
    """Approve a draft and email it. One use per draft."""
    settings = get_settings()

    # --- 1. Body size ------------------------------------------------------
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Request body too large.")

    # --- 2. Rate limit -----------------------------------------------------
    # Before the token check, on purpose. See the module docstring.
    peer = request.client.host if request.client else "unknown"
    resolved_ip = client_ip(peer, request.headers.get("x-forwarded-for"), settings)

    allowed, retry_after = _approvals.check(f"approve:{resolved_ip}")
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many approvals from this connection. Try again later.",
            headers={"retry-after": str(retry_after)},
        )

    # --- 3. Token ----------------------------------------------------------
    # Constant-time against the stored hash. `==` on digests leaks length and
    # prefix through response timing; hmac.compare_digest does not.
    async with pool.session_scope() as session:
        row = (
            await session.execute(
                _token_lookup_sql(),
                {
                    "id": message_id,
                    "token_hash": contact.hash_token(payload.token),
                },
            )
        ).fetchone()

    if row is None or not hmac.compare_digest(
        row.approval_token_hash or "", contact.hash_token(payload.token)
    ):
        # No distinction between "no such id", "wrong token" and "wrong IP".
        log.info("approval refused", extra={"message_id": message_id})
        response.status_code = status.HTTP_403_FORBIDDEN
        return SendMessageResponse(sent=False, message_id=message_id, reason=FORBIDDEN)

    # --- 4. IP -------------------------------------------------------------
    # Compared after the token, so the two factors are independent: knowing one
    # tells an attacker nothing about the other.
    if not _ip_matches(row.ip_hash, resolved_ip, settings):
        log.info("approval refused: different network", extra={"message_id": message_id})
        response.status_code = status.HTTP_403_FORBIDDEN
        return SendMessageResponse(sent=False, message_id=message_id, reason=FORBIDDEN)

    # --- 5. Status and expiry ----------------------------------------------
    now_expired = row.expires_at is None or row.expires_at <= _utcnow()
    if now_expired:
        await message_queries.mark_expired(message_id)
        response.status_code = status.HTTP_410_GONE
        return SendMessageResponse(
            sent=False,
            message_id=message_id,
            reason="That message has expired. Please write it again.",
        )

    if row.status != "pending":
        # Already sent, already failed, or claimed by a concurrent request.
        response.status_code = status.HTTP_409_CONFLICT
        return SendMessageResponse(
            sent=False, message_id=message_id, reason="That message has already been handled."
        )

    # --- Configuration -----------------------------------------------------
    # Refuse loudly rather than report a send that was dropped.
    if not settings.email_enabled:
        log.error("send attempted with email unconfigured")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email is not configured on this site right now.",
        )

    # --- 6. Daily cap ------------------------------------------------------
    reserved = await message_queries.reserve_daily_send(settings.daily_send_cap)
    if reserved is None:
        log.info("daily send cap reached")
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        return SendMessageResponse(
            sent=False,
            message_id=message_id,
            reason=(
                "The owner is receiving a high volume of messages and has reached "
                "today's limit. Please try again tomorrow."
            ),
        )

    # --- 7. Atomic claim ---------------------------------------------------
    claimed = await message_queries.claim_pending(message_id)
    if claimed is None:
        await message_queries.release_daily_send()
        response.status_code = status.HTTP_409_CONFLICT
        return SendMessageResponse(
            sent=False, message_id=message_id, reason="That message has already been handled."
        )

    # --- 8. Send -----------------------------------------------------------
    try:
        notification = build_notification(
            to=settings.contact_notify_email,
            reply_to=contact.normalise_email(row.email),
            sender_name=settings.resend_from,
            visitor_name=claimed["name"],
            visitor_email=row.email,
            body=claimed["body"],
        )
        provider_id = await send_notification(notification, settings)
    except (EmailError, contact.DraftError) as exc:
        await message_queries.release_daily_send()
        await message_queries.mark_failed(message_id, type(exc).__name__)
        log.error("send failed: %s", exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The message could not be sent. Please try again later.",
        ) from exc

    await message_queries.mark_sent(message_id, provider_id)

    log.info(
        "message sent",
        extra={"message_id": message_id, "reserved": reserved, "provider_id": provider_id},
    )
    return SendMessageResponse(sent=True, message_id=message_id)


@router.get("/messages/{message_id}", response_model=DraftSummary)
async def get_message(message_id: int) -> DraftSummary:
    """Fetch a draft for the approve control. No token, deliberately.

    If the browser lost the token the draft is unapprovable, and reissuing one
    would let a page reload silently extend a capability meant to expire.
    """
    draft = await message_queries.get_draft(message_id)
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such message.")

    return DraftSummary(
        id=draft["id"],
        name=draft["name"],
        email=draft["email"],
        body=draft["body"],
        status=draft["status"],
        created_at=draft["created_at"].isoformat(),
        expires_at=draft["expires_at"].isoformat(),
    )


def _token_lookup_sql() -> object:
    """The lookup for step 3.

    Hashing happens in SQL and the digest is compared with `hmac.compare_digest`
    in Python. The redundant re-hash of `payload.token` is what the comparison
    uses; the SQL comparison is what stops a timing difference distinguishing
    "no such id" from "wrong token" at the database.
    """
    from sqlalchemy import text

    return text(
        """
        SELECT id, name, email, body, status, expires_at, ip_hash, approval_token_hash
        FROM messages
        WHERE id = :id AND approval_token_hash = :token_hash
        """
    )


def _ip_matches(stored_hash: str | None, resolved_ip: str, settings) -> bool:
    """Whether the stored hash matches the resolved address."""
    if stored_hash is None:
        return False
    candidate = hash_from_settings(resolved_ip, settings)
    if candidate is None:
        return False
    return hmac.compare_digest(stored_hash, candidate)


def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)
