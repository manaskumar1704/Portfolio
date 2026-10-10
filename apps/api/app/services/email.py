"""compose the notification email, and hand it to Resend

The only file in the project that imports the Resend SDK, and the only one that
makes an outbound request on behalf of a visitor.

## Why it is separate from `contact.py`

`contact.py` drafts; this sends. Keeping them apart means the tool layer cannot
reach a send by accident — `draft_message` imports the drafter and has no path to
this module, which `test_no_send_in_p6.py` asserts structurally.

## Resend takes structured fields, so injection is bounded anyway

The SDK builds the MIME message from `subject`, `text` and `html` arguments
rather than from a raw string we concatenate. A newline in a name is therefore
not an SMTP header injection: there is no header to break. It is stripped anyway,
because control characters in a display name are a sign of something odd and
there is no reason to pass them through.

## The sender

`onboarding@resend.dev` only delivers to the account's own address. That is a
deliberate starting point: the smoke test works, and switching to a verified
domain is an environment variable rather than a code change.

`reply_to` is the visitor's validated address, so a reply from the owner's inbox
goes straight back to the person who wrote it. That is the whole reason the
visitor's address is captured at all.
"""

import re
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

ENDPOINT = "https://api.resend.com/emails"

# Control characters, minus tab and newline. A name or address carrying one is
# either a bug or an attempt at something.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Long enough for a long name plus a subject, short enough that a body stuffed
# into the subject is rejected by the API rather than silently delivered.
MAX_SUBJECT_CHARS = 120

# Resend's own limit is 40 MB; this is far below it and far above anything a
# visitor writes.
MAX_BODY_CHARS = 10_000


class EmailError(RuntimeError):
    """The send failed. The message is safe to log; it never contains a body."""

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Notification:
    """A message ready to send. Built by `build_notification`."""

    to: str
    subject: str
    text: str
    html: str
    reply_to: str


def clean_header_value(value: str, limit: int) -> str:
    """Strip control characters, collapse whitespace, and cap the length."""
    cleaned = _CONTROL.sub("", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"

    return cleaned


def escape_html(value: str) -> str:
    """Escape the five characters that matter in HTML text and attributes.

    The visitor's name and message go into the HTML body. Resend's renderer
    treats them as text once escaped, so a message containing `<script>` reaches
    the owner's mail client as the words rather than as markup.
    """
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def build_notification(
    *,
    to: str,
    reply_to: str,
    sender_name: str,
    visitor_name: str,
    visitor_email: str,
    body: str,
) -> Notification:
    """Assemble the notification. Pure, so it is testable without a network."""
    safe_name = clean_header_value(visitor_name, 200)
    safe_body = body.strip()[:MAX_BODY_CHARS]

    subject = clean_header_value(f"Portfolio contact from {safe_name}", MAX_SUBJECT_CHARS)

    text = (
        f"A visitor sent a message through the portfolio site.\n\n"
        f"Name:    {safe_name}\n"
        f"Email:   {visitor_email}\n"
        f"Reply to this email to reach them directly.\n\n"
        f"---\n{safe_body}\n"
    )

    html = (
        "<p>A visitor sent a message through the portfolio site.</p>"
        f"<p><strong>Name:</strong> {escape_html(safe_name)}<br>"
        f"<strong>Email:</strong> "
        f'<a href="mailto:{escape_html(visitor_email)}">{escape_html(visitor_email)}</a>'
        "</p>"
        "<p>Reply to this email to reach them directly.</p>"
        f"<hr><p>{escape_html(safe_body).replace(chr(10), '<br>')}</p>"
    )

    return Notification(
        to=to,
        subject=subject,
        text=text,
        html=html,
        reply_to=reply_to,
    )


class ResendResponse(BaseModel):
    """Only the fields we use. Resend returns more."""

    id: str = ""
    message: str = ""


async def send_notification(
    notification: Notification,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Send it. Returns the provider's id.

    Raises `EmailError` with a message that is safe to log: no API key, no
    message body, no visitor name. The caller is expected to record `failed`
    rather than retry blindly — Resend's 429 means the daily quota, and retrying
    immediately is how a quota turns into a suspension.

    One `httpx.AsyncClient` serves both the live call and the tests, which pass a
    client with a `MockTransport`. That is why no SDK-level client injection
    exists: the HTTP boundary is the seam, and it is the one worth having.
    """
    owns_client = client is None
    http = client or httpx.AsyncClient()

    try:
        response = await http.post(
            ENDPOINT,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.resend_from,
                "to": [notification.to],
                "subject": notification.subject,
                "text": notification.text,
                "html": notification.html,
                "reply_to": notification.reply_to,
            },
            timeout=httpx.Timeout(15.0, connect=5.0),
        )

        if response.status_code >= 400:
            detail = _safe_detail(response)
            log.error(
                "resend rejected the message",
                extra={"status": response.status_code, "detail": detail},
            )
            if response.status_code == 429:
                raise EmailError(
                    "The mail provider's daily quota is exhausted. Try again tomorrow.",
                    status=429,
                )
            raise EmailError(
                f"The mail provider rejected the message ({detail}).", status=response.status_code
            )

        payload: dict[str, Any] = response.json()
        message_id = ResendResponse(**payload).id
        log.info("notification sent", extra={"provider_id": message_id})
        return message_id
    except httpx.TimeoutException as exc:
        log.error("resend timed out")
        raise EmailError("The mail provider did not respond in time.") from exc
    except httpx.HTTPError as exc:
        # The exception's message can contain the URL, which here has no token
        # in it, but the request headers do — so nothing from the request is
        # included.
        log.error("resend unreachable: %s", type(exc).__name__)
        raise EmailError("Could not reach the mail provider.") from exc
    finally:
        if owns_client:
            await http.aclose()


def _safe_detail(response: httpx.Response) -> str:
    """The provider's error *code*, never its message.

    Resend answers a validation error like `{"message": "Bad request: <the
    submitted subject and body>", "name": "validation_error"}`. The message is
    the submitted content quoted back, so putting it in an exception means the
    visitor's message lands in a log line — truncating does not fix that, it
    just makes it a shorter copy of the same leak.

    The `name` is a slug (`validation_error`, `invalid_from_address`,
    `missing_api_key`) and contains none of the submitted fields. That is the
    whole diagnostic value anyway; the status code is already alongside it.
    """
    try:
        payload = response.json()
    except ValueError:
        return "no detail"

    name = payload.get("name")
    if not name:
        return "unknown error"

    # A slug is `[a-z0-9_]`; anything else is content smuggled into the field.
    if not re.fullmatch(r"[a-z0-9_]{1,40}", str(name)):
        return "unknown error"

    return str(name)
