"""POST /messages/* — the draft lifecycle: create, edit, cancel, send.

## Issuers and consumers

Two issuers write drafts: the `draft_message` tool (model-driven, via the chat
stream) and `POST /messages/drafts` (the contact form, model-free). Both bind a
salted IP hash at creation and give the browser the plaintext token; the server
keeps only its SHA-256.

Three routes act on a draft — edit, cancel, send — and they run the same four
capability checks, in the same order, through the shared `authorise` helper:
token (constant-time against the stored hash), IP (salted digest), expiry,
`pending`. Create issues a token and needs none; acting on a draft is what is
protected.

## lifecycle routes vs send, for refusals

`send` predates the other two and answers refusals in-band (its response model
already carries `sent`/`reason`). The edit and cancel routes raise
`HTTPException` with the same codes and the same words; the frontend's
reason-reader accepts either shape.

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

The send's step 7 is one statement, `UPDATE ... WHERE id = :id AND status = 'pending'`.
Two concurrent requests both evaluate the WHERE; the row lock means exactly one
sees `pending` and the other updates zero rows. A double-click, a browser retry
and an attacker replaying a captured token all land on the same 409. Edit and
cancel end with the same one-statement guard in their own UPDATE, so three
racing lifecycle actions pick exactly one winner per state change.

## Nothing here logs a token

Not in the access log, not in an error, not in a response body. The token is a
capability and the only place it is ever readable is the browser that received
it in the `draft` event.
"""

import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.client_ip import client_ip, current_client_ip, hash_from_settings
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.ratelimit import RateLimiter
from app.db import pool
from app.db.queries import messages as message_queries
from app.schemas.message import (
    CancelDraftRequest,
    CancelDraftResponse,
    CreateDraftRequest,
    CreateDraftResponse,
    DraftSummary,
    EditDraftRequest,
    SendMessageRequest,
    SendMessageResponse,
)
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


class _Refusal(Exception):
    """A capability check failed.

    The code and reason pair the three lifecycle answers share: 403 for the
    three indistinguishable misses (no such id, wrong token, different network),
    410 for expiry, 409 for a draft already handled. `send` returns its refusal
    in-band because its response model already has the shape; the edit and
    cancel routes raise `HTTPException` with the same code and words.
    """

    def __init__(self, status_code: int, reason: str):
        super().__init__(reason)
        self.status_code = status_code
        self.reason = reason


async def authorise(
    message_id: int,
    token: str,
    resolved_ip: str,
    settings,
) -> dict:
    """Token, IP, expiry, pending — in that order, or `_Refusal`.

    Shared by send, edit and cancel. Returns the row the checks passed on —
    send needs its `ip_hash` for the per-connection budget (ADR 0011). The
    steps below describe what each route once checked inline; the reason they
    are now one function is that a fourth route would otherwise mean
    re-implementing a race-sensitive sequence, and one implementation means
    one place to keep it honest.
    """
    # Constant-time against the stored hash. `==` on digests leaks length and
    # prefix through response timing; hmac.compare_digest does not. The SQL
    # equality stops a timing difference distinguishing "no such id" from
    # "wrong token" at the database; the Python comparison is what the response
    # actually trusts.
    async with pool.session_scope() as session:
        row = (
            await session.execute(
                _token_lookup_sql(),
                {
                    "id": message_id,
                    "token_hash": contact.hash_token(token),
                },
            )
        ).fetchone()

    if row is None or not hmac.compare_digest(
        row.approval_token_hash or "", contact.hash_token(token)
    ):
        # No distinction between "no such id", "wrong token" and "wrong IP".
        log.info("capability refused", extra={"message_id": message_id})
        raise _Refusal(status.HTTP_403_FORBIDDEN, FORBIDDEN)

    # Compared after the token, so the two factors are independent: knowing one
    # tells an attacker nothing about the other.
    if not _ip_matches(row.ip_hash, resolved_ip, settings):
        log.info("capability refused: different network", extra={"message_id": message_id})
        raise _Refusal(status.HTTP_403_FORBIDDEN, FORBIDDEN)

    now_expired = row.expires_at is None or row.expires_at <= datetime.now(UTC)
    if now_expired:
        await message_queries.mark_expired(message_id)
        raise _Refusal(
            status.HTTP_410_GONE,
            "That message has expired. Please write it again.",
        )

    if row.status != "pending":
        # Already sent, already failed, cancelled, or claimed concurrently.
        raise _Refusal(
            status.HTTP_409_CONFLICT,
            "That message has already been handled.",
        )

    return {
        "id": row.id,
        "ip_hash": row.ip_hash,
    }


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
    resolved_ip = _resolved_ip(request, settings)

    allowed, retry_after = _approvals.check(f"approve:{resolved_ip}")
    if not allowed:
        raise _too_many(retry_after)

    # --- 3 to 5. Token, IP, expiry, pending -------------------------------
    # Shared with the edit and cancel routes: `authorise` raises `_Refusal`,
    # which converts back to this route's in-band response shape. The row it
    # returns carries the draft's `ip_hash` — the actor the per-connection
    # budget counts below.
    try:
        checked = await authorise(message_id, payload.token, resolved_ip, settings)
    except _Refusal as refusal:
        log.info("approval refused", extra={"message_id": message_id})
        response.status_code = refusal.status_code
        return SendMessageResponse(sent=False, message_id=message_id, reason=refusal.reason)

    # --- Configuration -----------------------------------------------------
    # Refuse loudly rather than report a send that was dropped.
    if not settings.email_enabled:
        log.error("send attempted with email unconfigured")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email is not configured on this site right now.",
        )

    # --- 6. Caps. Per-connection first (ADR 0011): the cheap local gate
    # rejects the flood before touching the shared counter. If the global cap
    # then refuses, the visitor's own reservation is given back — it blocked
    # for a reason that was never theirs.
    reserved_ip = await message_queries.reserve_ip_send(
        checked["ip_hash"], settings.ip_daily_send_cap
    )
    if not reserved_ip:
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        return SendMessageResponse(
            sent=False,
            message_id=message_id,
            reason=(
                "That connection has reached today's sending limit. Please try again tomorrow."
            ),
        )

    reserved = await message_queries.reserve_daily_send(settings.daily_send_cap)
    if reserved is None:
        await message_queries.release_ip_send(checked["ip_hash"])
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
        await message_queries.release_ip_send(checked["ip_hash"])
        response.status_code = status.HTTP_409_CONFLICT
        return SendMessageResponse(
            sent=False, message_id=message_id, reason="That message has already been handled."
        )

    # --- 8. Send -----------------------------------------------------------
    try:
        notification = build_notification(
            to=settings.contact_notify_email,
            reply_to=contact.normalise_email(claimed["email"]),
            sender_name=settings.resend_from,
            visitor_name=claimed["name"],
            visitor_email=claimed["email"],
            body=claimed["body"],
            company=claimed["company"],
            role=claimed["role"],
            subject=claimed["subject"],
        )
        provider_id = await send_notification(notification, settings)
    except (EmailError, contact.DraftError) as exc:
        await message_queries.release_daily_send()
        await message_queries.release_ip_send(checked["ip_hash"])
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

    return _summary(draft)


@router.post("/messages/drafts", status_code=201, response_model=CreateDraftResponse)
async def create_draft(payload: CreateDraftRequest, request: Request) -> CreateDraftResponse:
    """The form's issuer: same row, same token mechanics, no model involved.

    Create *issues* the token and so requires none — its protection is the
    per-IP limiter (shared with approvals) plus the salted-IP binding every
    draft carries. Anyone can create a draft; only the connection that created
    one can ever act on it.
    """
    settings = get_settings()
    resolved_ip = _resolved_ip(request, settings)

    allowed, retry_after = _approvals.check(f"approve:{resolved_ip}")
    if not allowed:
        raise _too_many(retry_after)

    # The service reads the visitor's address from the request context, the
    # same channel the chat route sets for the tool path. Set here and nowhere
    # else; an argument on `create_draft` would be a trust boundary bypassed.
    current_client_ip.set(resolved_ip)

    try:
        draft = await contact.create_draft(
            payload.name,
            payload.sender_email,
            payload.body,
            company=payload.company,
            role=payload.role,
            subject=payload.subject,
        )
    except contact.DraftError as exc:
        # The message is the one the service wrote for the visitor: a fixable
        # content problem, with nothing about rate limits hidden in it.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    log.info("draft created via form", extra={"message_id": draft.id})
    return CreateDraftResponse(
        id=draft.id,
        name=draft.name,
        sender_email=draft.email,
        body=draft.body,
        expires_at=draft.expires_at.isoformat(),
        token=draft.token,
    )


@router.patch("/messages/{message_id}", response_model=DraftSummary)
async def edit_message(
    message_id: int, payload: EditDraftRequest, request: Request
) -> DraftSummary:
    """Change a pending draft's body. The token is used, not rotated."""
    settings = get_settings()
    resolved_ip = _resolved_ip(request, settings)

    allowed, retry_after = _approvals.check(f"approve:{resolved_ip}")
    if not allowed:
        raise _too_many(retry_after)

    await _authorised(message_id, payload.token, resolved_ip, settings)

    row = await message_queries.update_pending_body(message_id, payload.body)
    if row is None:
        # Authorise said pending; the update's own guard says it no longer is —
        # a send or cancel won the race in between.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That message has already been handled.",
        )

    return _summary(row)


@router.post("/messages/{message_id}/cancel", response_model=CancelDraftResponse)
async def cancel_message(
    message_id: int, payload: CancelDraftRequest, request: Request
) -> CancelDraftResponse:
    """Withdraw a pending draft. Bounded by the same four checks as send."""
    settings = get_settings()
    resolved_ip = _resolved_ip(request, settings)

    allowed, retry_after = _approvals.check(f"approve:{resolved_ip}")
    if not allowed:
        raise _too_many(retry_after)

    await _authorised(message_id, payload.token, resolved_ip, settings)

    if not await message_queries.cancel_pending(message_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That message has already been handled.",
        )

    return CancelDraftResponse(cancelled=True, message_id=message_id)


async def _authorised(message_id: int, token: str, resolved_ip: str, settings) -> None:
    """`authorise` with the `_Refusal` → `HTTPException` conversion."""
    try:
        await authorise(message_id, token, resolved_ip, settings)
    except _Refusal as refusal:
        raise HTTPException(refusal.status_code, refusal.reason) from refusal


def _too_many(retry_after: int) -> HTTPException:
    """The shared per-IP budget, spent. Same words on every route that spends it."""
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many attempts from this connection just now. Try again later.",
        headers={"retry-after": str(retry_after)},
    )


def _resolved_ip(request: Request, settings) -> str:
    """The visitor's address for a lifecycle request, normalised."""
    peer = request.client.host if request.client else "unknown"
    return client_ip(peer, request.headers.get("x-forwarded-for"), settings)


def _summary(row: dict) -> DraftSummary:
    """The row→wire shape both GET and PATCH answer with (no token, ever)."""
    return DraftSummary(
        id=row["id"],
        name=row["name"],
        sender_email=row["email"],
        body=row["body"],
        status=row["status"],
        created_at=row["created_at"].isoformat(),
        expires_at=row["expires_at"].isoformat(),
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
