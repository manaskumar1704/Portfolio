"""Email composition: escaping, header safety, and the Resend call.

No network. The provider boundary is an `httpx` client with a `MockTransport`, so
these assert what was *sent* rather than what Resend happened to accept.

## What is actually dangerous in an email

Header injection is the classic one: a newline in a display name breaks the
`Subject:` header and lets a sender inject their own fields. That risk is
bounded here because the SDK builds the MIME message from structured
`subject`/`text`/`html` arguments rather than from a string we concatenate — so
there is no header for a newline to break. Control characters are stripped
anyway, because their presence is a signal of something odd.

The one that is genuinely live is HTML: the visitor's name and message go into
the HTML body, and a message containing `<script>` would otherwise be markup in
the owner's mail client.
"""

import httpx
import pytest

from app.core.config import get_settings
from app.services.email import (
    MAX_SUBJECT_CHARS,
    EmailError,
    build_notification,
    clean_header_value,
    escape_html,
    send_notification,
)

OWNER = "owner@example.com"
VISITOR_EMAIL = "recruiter@example.com"


def make_settings(**overrides):
    settings = get_settings()
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def notify(**overrides):
    kwargs = {
        "to": OWNER,
        "reply_to": VISITOR_EMAIL,
        "sender_name": "onboarding@resend.dev",
        "visitor_name": "Ada Lovelace",
        "visitor_email": VISITOR_EMAIL,
        "body": "I would like to talk about a role.",
    }
    kwargs.update(overrides)
    return build_notification(**kwargs)


def client_returning(status: int, payload: dict | None = None, **headers) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload or {}, headers=headers)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def capturing_client(captured: dict, status: int = 200, payload: dict | None = None):
    """A client that records the request it was handed."""

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(status, json=payload or {"id": "msg_1"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- Header safety ----------------------------------------------------------


def test_newlines_are_stripped_from_a_name() -> None:
    """The classic injection: a name that tries to close the header."""
    cleaned = clean_header_value("Ada\r\nBcc: victim@example.com", 200)

    assert "\r" not in cleaned
    assert "\n" not in cleaned
    assert "Bcc" in cleaned, "the text is kept; only the control characters go"


def test_null_bytes_are_stripped() -> None:
    assert "\x00" not in clean_header_value("Ada\x00Lovelace", 200)


def test_whitespace_runs_are_collapsed() -> None:
    """Otherwise a folded header is possible even without a newline."""
    assert clean_header_value("Ada   \t  Lovelace", 200) == "Ada Lovelace"


def test_a_long_value_is_truncated_not_dropped() -> None:
    cleaned = clean_header_value("x" * 300, 100)

    assert len(cleaned) <= 100
    assert cleaned.endswith("…")


def test_a_display_name_attempt_cannot_inject_a_header() -> None:
    """End to end: the newline does not survive into the subject."""
    notification = notify(visitor_name="Ada\r\nX-Injected: yes")

    assert "\r" not in notification.subject
    assert "\n" not in notification.subject


def test_a_long_name_does_not_produce_a_long_subject() -> None:
    notification = notify(visitor_name="A" * 500)

    assert len(notification.subject) <= MAX_SUBJECT_CHARS


# --- HTML escaping ----------------------------------------------------------


def test_html_special_characters_are_escaped() -> None:
    assert escape_html('<script>alert("x")</script>') == (
        "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"
    )


def test_ampersands_are_escaped_first() -> None:
    """Otherwise `&lt;` in the source becomes `<` in the output."""
    assert escape_html("&lt;") == "&amp;lt;"


def test_a_script_tag_in_the_message_is_not_markup() -> None:
    """The live injection: a visitor's words into the owner's mail client."""
    notification = notify(body="<img src=x onerror=alert(1)>")

    assert "<img" not in notification.html
    assert "&lt;img" in notification.html


def test_a_script_tag_in_the_name_is_not_markup() -> None:
    notification = notify(visitor_name="<script>alert(1)</script>")

    assert "<script>" not in notification.html


def test_the_plain_text_version_keeps_the_original_text() -> None:
    """Escaping is for the HTML rendering only. The text part stays readable."""
    notification = notify(body="5 < 6 and 7 > 3")

    assert "5 < 6 and 7 > 3" in notification.text


# --- Composition ------------------------------------------------------------


def test_the_subject_names_the_sender() -> None:
    assert "Ada Lovelace" in notify().subject


def test_the_reply_to_is_the_visitor() -> None:
    """The whole reason the visitor's address is captured."""
    assert notify().reply_to == VISITOR_EMAIL


def test_the_message_body_is_included() -> None:
    assert "I would like to talk about a role." in notify().text


def test_the_visitor_address_is_in_the_body() -> None:
    assert VISITOR_EMAIL in notify().text


def test_newlines_become_line_breaks_in_html() -> None:
    """Otherwise a multi-line message renders as one paragraph."""
    notification = notify(body="Line one.\nLine two.")

    assert "<br>" in notification.html


def test_an_oversized_body_is_truncated() -> None:
    notification = notify(body="x" * 20_000)

    assert len(notification.text) < 20_000


# --- Sending ----------------------------------------------------------------


async def test_a_successful_send_returns_the_provider_id() -> None:
    client = client_returning(200, {"id": "msg_123"})

    message_id = await send_notification(notify(), make_settings(), client)

    assert message_id == "msg_123"


async def test_the_request_carries_the_expected_fields() -> None:
    """What Resend receives, asserted at the boundary."""
    captured: dict = {}
    client = capturing_client(captured)

    await send_notification(notify(), make_settings(resend_api_key="re_test"), client)

    assert captured["body"]["to"] == [OWNER]
    assert captured["body"]["reply_to"] == VISITOR_EMAIL
    assert captured["body"]["from"] == "onboarding@resend.dev"
    assert captured["auth"] == "Bearer re_test"


async def test_a_quota_refusal_says_try_tomorrow() -> None:
    """429 from Resend means the daily quota, and retrying makes it worse."""
    client = client_returning(429, {"message": "quota exceeded"})

    with pytest.raises(EmailError) as exc:
        await send_notification(notify(), make_settings(), client)

    assert "tomorrow" in str(exc.value).lower()
    assert exc.value.status == 429


async def test_a_rejection_does_not_echo_the_message_back() -> None:
    """Resend quotes submitted fields on a validation error."""
    secret = "my salary expectation is 180k"
    client = client_returning(422, {"message": f"Bad request: {secret}"})

    with pytest.raises(EmailError) as exc:
        await send_notification(notify(body=secret), make_settings(), client)

    assert secret not in str(exc.value)


async def test_a_timeout_is_reported_plainly() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with pytest.raises(EmailError, match="did not respond"):
        await send_notification(notify(), make_settings(), client)


async def test_an_unreachable_provider_is_reported_plainly() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with pytest.raises(EmailError, match="Could not reach"):
        await send_notification(notify(), make_settings(), client)


async def test_no_error_message_contains_the_api_key() -> None:
    """The key is in the Authorization header; an exception must not carry it."""
    client = client_returning(500, {"message": "server error"})

    with pytest.raises(EmailError) as exc:
        await send_notification(notify(), make_settings(resend_api_key="re_secret"), client)

    assert "re_secret" not in str(exc.value)
    assert "Bearer" not in str(exc.value)


async def test_a_malformed_response_is_not_fatal() -> None:
    """Resend returning something unexpected should not read as a success."""
    client = client_returning(200, {"unexpected": "shape"})

    message_id = await send_notification(notify(), make_settings(), client)

    assert message_id == ""


# --- The sender -------------------------------------------------------------


def test_the_default_sender_only_reaches_the_owner() -> None:
    """Documented Resend behaviour: onboarding@resend.dev delivers to the
    account address only. A real recruiter cannot receive anything until a
    domain is verified, which is why RESEND_FROM is a setting."""
    assert get_settings().resend_from == "onboarding@resend.dev"


def test_the_sender_is_configurable() -> None:
    """It has to be, or verifying a domain would be a code change."""
    settings = make_settings(resend_from="hello@manas.dev")

    assert settings.resend_from == "hello@manas.dev"
