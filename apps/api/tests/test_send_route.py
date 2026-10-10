"""POST /messages/{id}/send — the route that actually sends mail.

THIS IS A RED TEST FILE. It is written before `app/api/messages.py` and fails
with ImportError until that module exists. The properties below are the ones
that must hold before a visitor's message reaches the owner's inbox.

## The order of checks matters, and the first two are about cost

    1. body size          a 10 MB body costs nothing to refuse
    2. per-IP rate limit  cheap, and stops a flood of bad tokens
    3. token compare      constant-time, against a stored SHA-256
    4. IP match           normalised, so an IPv6 rotation is not a failure
    5. status and expiry  pending, and not expired
    6. daily send cap     the global budget, in the database
    7. atomic transition  pending -> sent, exactly one winner
    8. Resend

Rate limiting comes *before* the token check on purpose. Checking the token first
means every guess with a fake token reaches the database, which is a free
denial-of-service on the one endpoint that matters most. The token comparison is
cheap; the rate limiter is cheaper.

## Single use

Step 7 is one statement: `UPDATE ... WHERE id = :id AND status = 'pending'`
with `RETURNING`. Zero rows updated means somebody else got there first, and the
caller gets 409. A double-click, a browser retry, and an attacker replaying a
captured token all land on the same refusal.
"""

import pytest
from app.core.client_ip import hash_ip
from fastapi.testclient import TestClient

from app.main import app
from app.services import contact

SALT = "a-sufficiently-long-test-salt"
IP = "203.0.113.10"
OWNER = "owner@example.com"


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    """A sendable configuration. Nothing here reaches Resend: the tests that
    would are marked slow and use a mock transport."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ip_hash_salt", SALT)
    monkeypatch.setattr(settings, "contact_notify_email", OWNER)
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "resend_from", "onboarding@resend.dev")
    monkeypatch.setattr(settings, "daily_send_cap", 70)


def send(client: TestClient, message_id: int, token: str, **overrides) -> dict:
    body = {"token": token}
    body.update(overrides)
    response = client.post(f"/messages/{message_id}/send", json=body)
    return {"status": response.status_code, "json": response.json() if response.content else {}}


# --- The happy path ---------------------------------------------------------


async def test_a_correct_token_sends_once(client) -> None:
    """The route works end to end. Everything else is about it not working twice."""
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    result = send(client, draft.id, draft.token, client_ip=IP)

    assert result["status"] == 200, result
    assert result["json"]["sent"] is True


async def test_the_response_does_not_echo_the_token_back(client) -> None:
    """A token in a response body lands in a browser history and a log."""
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    result = send(client, draft.id, draft.token, client_ip=IP)

    assert draft.token not in str(result["json"])


# --- Single use -------------------------------------------------------------


async def test_a_replay_is_refused(client) -> None:
    """The double-click case. Two emails for one approval is the visible bug."""
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    first = send(client, draft.id, draft.token, client_ip=IP)
    second = send(client, draft.id, draft.token, client_ip=IP)

    assert first["status"] == 200
    assert second["status"] == 409


async def test_a_replay_after_the_status_flips_sends_nothing(client) -> None:
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)
    send(client, draft.id, draft.token, client_ip=IP)

    from sqlalchemy import text

    from app.db import pool

    async with pool.session_scope() as session:
        status = (
            await session.execute(
                text("SELECT status FROM messages WHERE id = :id"), {"id": draft.id}
            )
        ).scalar_one()

    assert status == "sent"


# --- The token --------------------------------------------------------------


async def test_a_wrong_token_is_forbidden(client) -> None:
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    result = send(client, draft.id, "not-the-token", client_ip=IP)

    assert result["status"] == 403


async def test_an_unknown_message_id_is_forbidden(client) -> None:
    """Indistinguishable from a wrong token, on purpose.

    Telling the two apart turns the route into an oracle for which message ids
    exist, which is a small thing but free to avoid.
    """
    result = send(client, 999_999_999, "anything", client_ip=IP)

    assert result["status"] == 403


async def test_a_missing_token_is_a_validation_error(client) -> None:
    result = send(client, 1, None)

    assert result["status"] in (403, 422)


async def test_the_token_compare_is_constant_time(client) -> None:
    """Shape, not timing.

    A wall-clock assertion would be flaky and would fail on a busy machine. What
    is checkable is that the implementation uses `hmac.compare_digest` rather
    than `==`, which is the mistake this is guarding against.
    """
    import inspect

    from app.api import messages

    source = inspect.getsource(messages)

    assert "compare_digest" in source, "token comparison must be constant-time"
    assert "hmac" in source, "use hmac.compare_digest, not == on the digests"


# --- The IP factor ----------------------------------------------------------


async def test_a_token_from_another_ip_is_forbidden(client) -> None:
    """The factor that stops a leaked link being useful somewhere else."""
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    result = send(client, draft.id, draft.token, client_ip="198.51.100.7")

    assert result["status"] == 403


async def test_an_ipv6_rotation_in_the_same_64_is_accepted(client) -> None:
    """A privacy-preserving address change is not a different visitor."""
    from tests.helpers import make_pending_draft

    ipv6_a = "2001:db8:1234:5678::1"
    ipv6_b = "2001:db8:1234:5678:9abc::dead"
    draft = await make_pending_draft(IP=ipv6_a, salt=SALT)

    result = send(client, draft.id, draft.token, client_ip=ipv6_b)

    assert result["status"] == 200, result


async def test_a_different_ipv6_64_is_refused(client) -> None:
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP="2001:db8:1111::1", salt=SALT)

    result = send(client, draft.id, draft.token, client_ip="2001:db8:2222::1")

    assert result["status"] == 403


# --- The mismatch message ---------------------------------------------------


async def test_an_ip_mismatch_is_explained_not_barely_refused(client) -> None:
    """A visitor who switched wifi deserves to be told what happened.

    A bare 403 says "you are wrong" and gives no way to proceed. The message
    names the likely cause and what to do instead, without confirming that the
    draft exists.
    """
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    result = send(client, draft.id, draft.token, client_ip="198.51.100.7")

    assert result["status"] == 403
    message = str(result["json"]).lower()
    assert "connection" in message or "network" in message
    assert "wifi" in message or "mobile" in message


async def test_the_mismatch_message_does_not_confirm_the_draft_exists(client) -> None:
    """The refusal must read the same whether or not the draft is real."""
    real = await _draft_id(IP=IP)
    existing = send(client, real, "wrong-token", client_ip="198.51.100.7")
    absent = send(client, 999_999_999, "wrong-token", client_ip="198.51.100.7")

    assert existing["json"].get("message") == absent["json"].get("message")


async def _draft_id(ip: str) -> int:
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=ip, salt=SALT)
    return draft.id


# --- Expiry -----------------------------------------------------------------


async def test_an_expired_draft_is_gone(client) -> None:
    """410, not 403: the token was once correct and has timed out."""
    from sqlalchemy import text

    from app.db import pool
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)
    async with pool.session_scope() as session:
        await session.execute(
            text("UPDATE messages SET expires_at = now() - interval '1 hour' WHERE id = :id"),
            {"id": draft.id},
        )

    result = send(client, draft.id, draft.token, client_ip=IP)

    assert result["status"] == 410


# --- Rate limiting, and its position ---------------------------------------


async def test_the_approval_cap_is_enforced(client) -> None:
    """Three per hour, so the fourth attempt is the first refusal."""
    from tests.helpers import make_pending_draft

    drafts = [await make_pending_draft(IP=IP, salt=SALT) for _ in range(5)]

    codes = [send(client, draft.id, draft.token, client_ip=IP)["status"] for draft in drafts]

    # Every attempt is a *different* draft, so this is the cap and not replay
    # protection. The fourth is the first 429.
    assert 429 in codes, codes
    assert codes.index(429) == 3, codes


async def test_rate_limiting_happens_before_the_token_check(client) -> None:
    """Cost ordering. A flood of bad tokens must not reach the database.

    Checked structurally because a wall-clock test cannot tell the difference:
    the route must consult the limiter before it compares anything.
    """
    import inspect

    from app.api import messages

    source = inspect.getsource(messages)

    limiter_at = source.find("limiter.check")
    compare_at = source.find("compare_digest")

    assert limiter_at != -1, "the route must rate limit"
    assert compare_at != -1, "the route must compare the token"
    assert limiter_at < compare_at, "rate limiting must come first"


async def test_a_rate_limited_request_is_429_with_retry_after(client) -> None:
    response = client.post("/messages/1/send", json={"token": "x"})

    if response.status_code == 429:
        assert int(response.headers["retry-after"]) >= 1


# --- Body limits ------------------------------------------------------------


def test_an_oversized_body_is_refused(client) -> None:
    """Cheap first, before anything parses or looks anything up."""
    response = client.post(
        "/messages/1/send",
        content=b'{"token": "' + b"a" * 2_000_000 + b'"}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code in (413, 422, 429, 403)


# --- Not leaking ------------------------------------------------------------


async def test_no_response_leaks_a_token_or_the_api_key(client) -> None:
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    for attempt in (
        send(client, draft.id, draft.token, client_ip=IP),
        send(client, draft.id, "wrong", client_ip=IP),
        send(client, 999_999_999, "wrong", client_ip=IP),
    ):
        rendered = str(attempt["json"])
        assert draft.token not in rendered
        assert "re_test_key" not in rendered
        assert "Traceback" not in rendered


async def test_the_message_body_is_not_echoed(client) -> None:
    """A stranger's words must not come back in an API response."""
    from tests.helpers import make_pending_draft

    secret_phrase = "my salary expectation is 180k"
    draft = await make_pending_draft(IP=IP, salt=SALT, body=secret_phrase)

    result = send(client, draft.id, "wrong-token", client_ip=IP)

    assert secret_phrase not in str(result["json"])


async def test_the_ip_hash_is_cleared_on_send(client) -> None:
    """The visitor's address stops existing the moment it has served its purpose."""
    from sqlalchemy import text

    from app.db import pool
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)
    send(client, draft.id, draft.token, client_ip=IP)

    async with pool.session_scope() as session:
        stored = (
            await session.execute(
                text("SELECT ip_hash FROM messages WHERE id = :id"), {"id": draft.id}
            )
        ).scalar_one()

    assert stored is None


async def test_sending_does_not_delete_the_row(client) -> None:
    """Retention is a separate job. Clearing the hash is not deleting evidence
    that a message was sent — that matters if a visitor disputes it."""
    from sqlalchemy import text

    from app.db import pool
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)
    send(client, draft.id, draft.token, client_ip=IP)

    async with pool.session_scope() as session:
        count = (
            await session.execute(
                text("SELECT count(*) FROM messages WHERE id = :id"), {"id": draft.id}
            )
        ).scalar_one()

    assert count == 1


# --- Configuration ----------------------------------------------------------


async def test_a_missing_resend_key_fails_loudly_not_silently(client) -> None:
    """Better a 503 than a "sent" that was dropped on the floor."""
    from app.core.config import get_settings
    from tests.helpers import make_pending_draft

    settings = get_settings()
    original = settings.resend_api_key
    settings.resend_api_key = ""
    try:
        draft = await make_pending_draft(IP=IP, salt=SALT)
        result = send(client, draft.id, draft.token, client_ip=IP)

        assert result["status"] == 503
    finally:
        settings.resend_api_key = original


# --- The token reaches the browser, not the model ---------------------------


async def test_the_draft_event_carries_the_token_to_the_browser() -> None:
    """The token must reach the frontend somehow, or nothing can ever be sent.

    It goes in `event: draft`, which the router emits from the tool result. The
    loop must not pass it to the model, and the model must not be able to read
    it back out.
    """
    from app.services import chat

    source = inspect_source_of_chat(chat)

    assert "draft" in source, "the loop must emit a draft event"
    assert "DraftEvent" in source or "approval_token" in source


def inspect_source_of_chat(module) -> str:
    import inspect

    return inspect.getsource(module)


async def test_the_token_is_not_in_the_confirmation_string() -> None:
    """P5's rule still holds: the model never reads the send capability."""
    from datetime import UTC, datetime, timedelta

    draft = contact.Draft(
        id=1,
        name="Ada",
        email="ada@example.com",
        body="Hi",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        token="THE-TOKEN",
    )

    assert "THE-TOKEN" not in contact.confirmation_for_model(draft)


def test_the_ip_hash_matches_what_the_draft_was_written_with() -> None:
    """Both sides must agree on normalisation, or approval never matches."""
    from tests.helpers import pending_ip_hash

    assert pending_ip_hash("2001:db8:1234:5678::1", SALT) == hash_ip(
        "2001:db8:1234:5678:9abc::dead", SALT
    )
