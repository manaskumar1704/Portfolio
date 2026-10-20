"""The draft lifecycle: create, edit, cancel — the routes around the send.

`test_send_route.py` owns the send refusals; this file owns the routes added in
the draft-lifecycle checkpoint. The properties that matter:

- the form's issuer writes the same row shape the tool's issuer does, bound to
  the connection that made it, with only the hash of the token stored;
- the context fields (company, role, subject) are stored only when offered, and
  never at the cost of the required three;
- edit and cancel are guarded by the same four checks as send, end with the same
  one-statement `WHERE status = 'pending'`, and do not rotate the token;
- cancelling clears the IP binding the moment withdrawal is recorded.
"""

import httpx
import pytest

from app.api.messages import FORBIDDEN
from app.core.ratelimit import RateLimiter
from app.main import app
from tests.helpers import clear_test_drafts, ensure_pool, pending_ip_hash, teardown_pool

SALT = "a-sufficiently-long-test-salt"
IP = "45.33.32.42"
OTHER_IP = "8.8.8.8"


@pytest.fixture
async def client():
    """Same loop as the test, no lifespan; identical reasoning to test_send_route."""
    from app.core.config import get_settings

    if not get_settings().database_url:
        pytest.skip("DATABASE_URL not set; the lifecycle routes need a database")

    await ensure_pool()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        try:
            yield http
        finally:
            await clear_test_drafts()
            await teardown_pool()


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    """Pinned credentials and a fresh limiter, as in test_send_route."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ip_hash_salt", SALT)
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", ["127.0.0.0/8", "::1/128"])
    monkeypatch.setattr(
        "app.api.messages._approvals",
        RateLimiter(per_minute=1000, burst=1000),
    )


async def _create(client: httpx.AsyncClient, ip: str = IP, **overrides) -> httpx.Response:
    """POST /messages/drafts with the form's full payload (or an override)."""
    payload = {
        "name": "Ada Lovelace",
        "sender_email": "ada@example.com",
        "body": "Hello from the form.",
        "company": "Analytical Engines Ltd",
        "role": "Principal Diagonalist",
        "subject": "Conference keynote",
        **overrides,
    }
    return await client.post(
        "/messages/drafts",
        json=payload,
        headers={"x-forwarded-for": ip},
    )


async def test_the_form_creates_a_row_the_visitor_can_act_on(client) -> None:
    response = await _create(client)

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["sender_email"] == "ada@example.com"
    assert body["token"], "the plaintext token must reach the browser"

    from sqlalchemy import text

    from app.db import pool

    async with pool.session_scope() as session:
        row = (
            await session.execute(
                text(
                    "SELECT status, email, company, role, subject, ip_hash, origin_ip "
                    "FROM messages WHERE id = :id"
                ),
                {"id": body["id"]},
            )
        ).fetchone()

    assert row.status == "pending"
    assert row.email == "ada@example.com"  # the column keeps its spelling
    assert row.company == "Analytical Engines Ltd"
    assert row.role == "Principal Diagonalist"
    assert row.subject == "Conference keynote"
    assert row.ip_hash == pending_ip_hash(IP, SALT)
    assert row.origin_ip is None, "no plaintext address is ever stored"


async def test_the_context_fields_are_optional(client) -> None:
    response = await _create(client, company=None, role=None, subject=None)

    assert response.status_code == 201
    assert "company" not in response.json()


async def test_an_invalid_sender_email_is_the_service_s_own_422(client) -> None:
    response = await _create(client, sender_email="not-an-address")

    assert response.status_code == 422
    assert "email" in response.json()["detail"].lower()


async def test_unknown_fields_are_refused(client) -> None:
    """`extra="forbid"` is the schema doing form-shaped input validation."""
    response = await _create(client, website="https://example.com")

    assert response.status_code == 422


async def test_edit_changes_the_body_and_keeps_the_token(client, monkeypatch) -> None:
    """Edit is authorised BY the token and must not rotate it.

    The proof that the token survived: the send still works with the *original*
    one after the edit. `fake_send` stubs the provider — the send is the
    assertion vehicle, not the thing under test.
    """
    from app.api import messages as messages_api

    async def fake_send(notification, config, client=None):
        return "provider-test-id"

    monkeypatch.setattr(messages_api, "send_notification", fake_send)

    created = (await _create(client)).json()
    message_id, token = created["id"], created["token"]

    response = await client.patch(
        f"/messages/{message_id}",
        json={"token": token, "body": "An edited body."},
        headers={"x-forwarded-for": IP},
    )

    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["body"] == "An edited body."
    assert summary["sender_email"] == "ada@example.com"

    send_after = await client.post(
        f"/messages/{message_id}/send",
        json={"token": token},
        headers={"x-forwarded-for": IP},
    )
    assert send_after.status_code == 200
    assert send_after.json()["sent"] is True


async def test_edit_with_the_wrong_token_is_the_shared_refusal(client) -> None:
    created = (await _create(client)).json()

    response = await client.patch(
        f"/messages/{created['id']}",
        json={"token": "wrong", "body": "…"},
        headers={"x-forwarded-for": IP},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == FORBIDDEN


async def test_edit_from_another_network_is_refused(client) -> None:
    created = (await _create(client)).json()

    response = await client.patch(
        f"/messages/{created['id']}",
        json={"token": created["token"], "body": "…"},
        headers={"x-forwarded-for": OTHER_IP},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == FORBIDDEN


async def test_cancel_withdraws_the_draft_and_clears_the_hash(client) -> None:
    from sqlalchemy import text

    from app.db import pool

    created = (await _create(client)).json()

    response = await client.post(
        f"/messages/{created['id']}/cancel",
        json={"token": created["token"]},
        headers={"x-forwarded-for": IP},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"cancelled": True, "message_id": created["id"], "reason": None}

    async with pool.session_scope() as session:
        row = (
            await session.execute(
                text("SELECT status, ip_hash FROM messages WHERE id = :id"),
                {"id": created["id"]},
            )
        ).fetchone()

    assert row.status == "cancelled"
    assert row.ip_hash is None, "a withdrawn draft has no use for the binding"


async def test_a_second_cancel_is_refused_like_a_replay(client) -> None:
    """Withdraw twice: the second is 403, not 409, on purpose.

    The first cancel nulls `ip_hash`, so the second request dies at the hash
    step with the shared refusal — the same shape the send route reports for a
    replay, for the same reason (test_send_route.py's replay test). No second
    withdrawal and no oracle: the visitor sees the same words as a wrong token.
    """
    created = (await _create(client)).json()
    first = await client.post(
        f"/messages/{created['id']}/cancel",
        json={"token": created["token"]},
        headers={"x-forwarded-for": IP},
    )
    assert first.status_code == 200

    second = await client.post(
        f"/messages/{created['id']}/cancel",
        json={"token": created["token"]},
        headers={"x-forwarded-for": IP},
    )

    assert second.status_code == 403
    assert second.json()["detail"] == FORBIDDEN


async def test_send_after_cancel_is_refused_at_the_hash_step(client) -> None:
    """The withdrawn draft sends nothing, and says why it can.

    Cancelling nulls `ip_hash`, so the refusal lands where a replay's does: at
    the IP step, 403, before status is consulted. Same shape, no email.
    """
    created = (await _create(client)).json()
    cancelled = await client.post(
        f"/messages/{created['id']}/cancel",
        json={"token": created["token"]},
        headers={"x-forwarded-for": IP},
    )
    assert cancelled.status_code == 200

    response = await client.post(
        f"/messages/{created['id']}/send",
        json={"token": created["token"]},
        headers={"x-forwarded-for": IP},
    )

    assert response.status_code == 403
    assert response.json()["sent"] is False


async def test_a_cancelled_row_is_never_the_model_s_to_recreate(client) -> None:
    """Withdrawal is a human action; nothing offers it through the registry."""
    from app.tools import registry

    assert "cancel_message" not in {spec.name for spec in registry.specs()}
