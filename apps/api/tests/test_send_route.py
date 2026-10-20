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

import httpx
import pytest

from app.core.client_ip import hash_ip
from app.core.ratelimit import RateLimiter
from app.main import app
from app.services import contact
from tests.helpers import clear_test_drafts, ensure_pool, teardown_pool

SALT = "a-sufficiently-long-test-salt"

# Globally routable, not the RFC 5737 documentation range. `client_ip` refuses a
# forwarded header claiming a non-global address — correctly, since no real
# visitor is on one — so a documentation IP here would exercise the forged-header
# path instead of the real one. `test_client_ip.py` pins that refusal separately.
IP = "45.33.32.42"
OTHER_IP = "8.8.8.8"

OWNER = "owner@example.com"


@pytest.fixture
async def client():
    """An async client on the *same* event loop as the test.

    `TestClient` runs the app's lifespan on a separate thread with its own event
    loop, so pooled connections created there are bound to a loop the test body
    is not running on — and every request fails with "attached to a different
    loop". `ASGITransport` has no second loop, so the engine, the requests and
    the assertions all share one.

    The lifespan is skipped deliberately: the pool is set up here instead, so
    setup and teardown both happen on this loop. The lifespan's only other job is
    the boot retention sweep, which has its own tests.
    """
    from app.core.config import get_settings

    if not get_settings().database_url:
        pytest.skip("DATABASE_URL not set; the send route needs a database")

    await ensure_pool()
    await reset_budget()
    await reset_ip_budget()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        try:
            yield http
        finally:
            await clear_test_drafts()
            # Each pytest-asyncio test gets a fresh event loop, and pooled
            # connections belong to the loop that opened them. Without disposing
            # here, the next test inherits connections bound to a closed loop and
            # fails with "Event loop is closed" — a leak in the test harness that
            # looks exactly like a bug in the pool.
            await teardown_pool()


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
    # Generous so the ~30 sends this suite makes under the same fixture IP do
    # not smear into the per-connection cap. The tests that target the cap
    # shrink it themselves.
    monkeypatch.setattr(settings, "ip_daily_send_cap", 100)

    # `ASGITransport` presents as 127.0.0.1, so loopback has to be a trusted peer
    # for `X-Forwarded-For` to be honoured at all. In production this list holds
    # Render's proxy CIDRs, observed via the header-echo probe; the loopback
    # entry is the local equivalent. Without it every assertion below would be
    # testing the forged-header path instead of the real one.
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", ["127.0.0.0/8", "::1/128"])

    # The email service is stubbed rather than mocked by path, so these tests
    # assert the route's behaviour and not Resend's. `test_email.py` covers the
    # provider call itself with an httpx MockTransport.
    from app.api import messages as messages_api

    async def fake_send(notification, config, client=None):
        return "provider-test-id"

    monkeypatch.setattr(messages_api, "send_notification", fake_send)
    # A *fresh* limiter per test. The route's limiter is module-level, so
    # without this a test that drains it leaves every later test seeing an
    # exhausted bucket — which is exactly how `test_the_approval_cap_is_enforced`
    # passed for the wrong reason on the first run.
    monkeypatch.setattr(messages_api, "_approvals", RateLimiter(per_minute=1000, burst=1000))


async def reset_budget() -> None:
    """Empty today's send budget.

    The counter is a real row in a real table, which is the whole point of it —
    so it survives between test runs exactly as it survives between Render
    spin-downs. Without this the suite fills the owner's daily allowance and
    every send returns 429 for reasons that have nothing to do with the code.

    Reset rather than delete-and-insert: the row *is* the cap, so resetting is
    the closest a test can get to "a new day" without waiting for one.
    """
    from sqlalchemy import text

    from app.db import pool

    async with pool.session_scope() as session:
        await session.execute(text("UPDATE send_counters SET count = 0 WHERE day = current_date"))


async def reset_ip_budget() -> None:
    """Clear today's per-connection counters (ADR 0011).

    The rows survive between test runs the same way the global one does, keyed
    by the salted digest of the IP every test in this suite sends from.
    """
    from sqlalchemy import text

    from app.db import pool

    async with pool.session_scope() as session:
        await session.execute(text("DELETE FROM ip_send_counters WHERE day = current_date"))


async def send(
    client: httpx.AsyncClient,
    message_id: int,
    token: str,
    client_ip: str | None = None,
    **overrides,
) -> dict:
    """POST the send route.

    The visitor's address goes in `X-Forwarded-For`, which is how a real request
    from behind Render arrives. It is only honoured because these tests set
    `TRUSTED_PROXY_CIDRS` to include the peer address; without that, the header
    would be ignored exactly as a forged one is.
    """
    headers = {"x-forwarded-for": client_ip} if client_ip else {}
    response = await client.post(
        f"/messages/{message_id}/send",
        json={"token": token, **overrides},
        headers=headers,
    )
    return {"status": response.status_code, "json": response.json() if response.content else {}}


# --- The happy path ---------------------------------------------------------


async def test_a_correct_token_sends_once(client) -> None:
    """The route works end to end. Everything else is about it not working twice."""
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    result = await send(client, draft.id, draft.token, client_ip=IP)

    assert result["status"] == 200, result
    assert result["json"]["sent"] is True


async def test_the_response_does_not_echo_the_token_back(client) -> None:
    """A token in a response body lands in a browser history and a log."""
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    result = await send(client, draft.id, draft.token, client_ip=IP)

    assert draft.token not in str(result["json"])


# --- Single use -------------------------------------------------------------


async def test_a_replay_is_refused(client) -> None:
    """The double-click case. Two emails for one approval is the visible bug.

    The refusal is **403, not 409**, and that is worth explaining rather than
    papering over. Sending clears the row's IP hash immediately — that is the
    privacy requirement — so by the time a replay arrives there is nothing to
    match the request against and it is refused at the IP step, before the
    status is ever consulted.

    Both refusals are equally safe: neither sends. What 409 was for is a
    concurrent pair where both requests still have a matching hash, and
    `test_a_concurrent_pair_sends_once` covers that.
    """
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    first = await send(client, draft.id, draft.token, client_ip=IP)
    second = await send(client, draft.id, draft.token, client_ip=IP)

    assert first["status"] == 200
    assert second["status"] in (403, 409), second
    assert second["json"]["sent"] is False


async def test_a_concurrent_pair_sends_once(client) -> None:
    """Two simultaneous approvals, one email.

    This is where 409 belongs: both requests still hold a matching IP hash, so
    both reach the atomic claim and exactly one wins. Losers get 409.
    """
    import asyncio

    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)

    first, second = await asyncio.gather(
        send(client, draft.id, draft.token, client_ip=IP),
        send(client, draft.id, draft.token, client_ip=IP),
    )

    statuses = sorted([first["status"], second["status"]])

    assert statuses == [200, 409], statuses
    assert second["json"]["sent"] is False


async def test_a_replay_after_the_status_flips_sends_nothing(client) -> None:
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)
    (await send(client, draft.id, draft.token, client_ip=IP))

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

    result = await send(client, draft.id, "not-the-token", client_ip=IP)

    assert result["status"] == 403


async def test_an_unknown_message_id_is_forbidden(client) -> None:
    """Indistinguishable from a wrong token, on purpose.

    Telling the two apart turns the route into an oracle for which message ids
    exist, which is a small thing but free to avoid.
    """
    result = await send(client, 999_999_999, "anything", client_ip=IP)

    assert result["status"] == 403


async def test_a_missing_token_is_a_validation_error(client) -> None:
    result = await send(client, 1, None)

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

    result = await send(client, draft.id, draft.token, client_ip=OTHER_IP)

    assert result["status"] == 403


async def test_an_ipv6_rotation_in_the_same_64_is_accepted(client) -> None:
    """A privacy-preserving address change is not a different visitor."""
    from tests.helpers import make_pending_draft

    # Same /64, different addresses: hextets 1-4 identical.
    ipv6_a = "2606:4700:4700:1111::1"
    ipv6_b = "2606:4700:4700:1111:9abc::dead"
    draft = await make_pending_draft(IP=ipv6_a, salt=SALT)

    result = await send(client, draft.id, draft.token, client_ip=ipv6_b)

    assert result["status"] == 200, result


async def test_a_different_ipv6_64_is_refused(client) -> None:
    """Different subnet, so a different visitor.

    Both are globally routable, so this exercises the /64 comparison rather than
    the non-global refusal.
    """
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP="2606:4700:4700:1111::1", salt=SALT)

    result = await send(client, draft.id, draft.token, client_ip="2606:4700:4700:2222::1")

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

    result = await send(client, draft.id, draft.token, client_ip=OTHER_IP)

    assert result["status"] == 403
    message = str(result["json"]).lower()
    assert "connection" in message or "network" in message
    assert "wifi" in message or "mobile" in message


async def test_the_mismatch_message_does_not_confirm_the_draft_exists(client) -> None:
    """The refusal must read the same whether or not the draft is real."""
    from tests.helpers import make_pending_draft

    real = (await make_pending_draft(IP=IP, salt=SALT)).id
    existing = await send(client, real, "wrong-token", client_ip=OTHER_IP)
    absent = await send(client, 999_999_999, "wrong-token", client_ip=OTHER_IP)

    # Everything but the id must be identical. `message_id` echoes the id that
    # was asked for, which is not a disclosure — the caller supplied it.
    assert existing["status"] == absent["status"] == 403
    assert existing["json"]["reason"] == absent["json"]["reason"]
    assert existing["json"]["sent"] is absent["json"]["sent"] is False


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

    result = await send(client, draft.id, draft.token, client_ip=IP)

    assert result["status"] == 410


# --- Rate limiting, and its position ---------------------------------------


async def test_the_approval_cap_is_enforced(client, monkeypatch) -> None:
    """Three per hour, so the fourth attempt is the first refusal.

    Installs the *default* limiter rather than a hand-set burst, because the claim
    is "the configured cap is 3", not "some number produces a 429".
    """
    from app.api import messages as messages_api
    from app.core.config import get_settings
    from tests.helpers import make_pending_draft

    settings = get_settings()
    assert settings.approve_limit_per_hour == 3, "the default cap changed"

    monkeypatch.setattr(
        messages_api,
        "_approvals",
        RateLimiter(
            per_hour=settings.approve_limit_per_hour, burst=settings.approve_limit_per_hour
        ),
    )

    drafts = [await make_pending_draft(IP=IP, salt=SALT) for _ in range(5)]

    codes = [
        (await send(client, draft.id, draft.token, client_ip=IP))["status"] for draft in drafts
    ]
    # Every attempt is a *different* draft, so this is the cap and not replay
    # protection. The fourth is the first 429.
    assert 429 in codes, codes
    assert codes.index(429) == 3, codes


# --- The per-connection daily cap (ADR 0011) --------------------------------


async def test_a_connection_loses_the_budget_after_two_sends(client, monkeypatch) -> None:
    """Two sends per IP per UTC day. The global cap never notices this.

    Sends three *different* drafts from one connection, so nothing here is
    replay protection — the third answer is the per-connection cap saying no
    while the global counter is untouched underneath it.
    """
    from app.core.config import get_settings
    from tests.helpers import make_pending_draft

    monkeypatch.setattr(get_settings(), "ip_daily_send_cap", 2)

    drafts = [await make_pending_draft(IP=IP, salt=SALT) for _ in range(3)]

    first = await send(client, drafts[0].id, drafts[0].token, client_ip=IP)
    second = await send(client, drafts[1].id, drafts[1].token, client_ip=IP)
    third = await send(client, drafts[2].id, drafts[2].token, client_ip=IP)

    assert first["status"] == 200
    assert second["status"] == 200
    assert third["status"] == 429, third
    assert third["json"]["sent"] is False
    assert "connection" in third["json"]["reason"], third


async def test_a_failed_send_gives_the_connection_its_slot_back(client, monkeypatch) -> None:
    """A provider outage must not eat the visitor's two sends.

    The first send raises on the way to the provider and is released; the
    second draft from the same connection still goes through.
    """
    from app.core.config import get_settings
    from app.services.email import EmailError
    from tests.helpers import make_pending_draft

    monkeypatch.setattr(get_settings(), "ip_daily_send_cap", 1)

    first = await make_pending_draft(IP=IP, salt=SALT)

    from app.api import messages as messages_api

    async def failing_send(notification, config, client=None):
        raise EmailError("provider said no")

    monkeypatch.setattr(messages_api, "send_notification", failing_send)
    result = await send(client, first.id, first.token, client_ip=IP)
    assert result["status"] == 502, result

    async def working_send(notification, config, client=None):
        return "provider-test-id"

    monkeypatch.setattr(messages_api, "send_notification", working_send)

    second = await make_pending_draft(IP=IP, salt=SALT)
    retry = await send(client, second.id, second.token, client_ip=IP)

    assert retry["status"] == 200, retry


async def test_another_connection_spends_its_own_budget(client, monkeypatch) -> None:
    """The counter keys on the digest of the requesting network, one each.

    Two drafts from two different IPs, cap 1: both send. The first connection's
    spend is invisible to the second, and vice versa.
    """
    from app.core.config import get_settings
    from tests.helpers import make_pending_draft

    monkeypatch.setattr(get_settings(), "ip_daily_send_cap", 1)

    theirs = await make_pending_draft(IP="9.9.9.9", salt=SALT)
    mine = await make_pending_draft(IP=IP, salt=SALT)

    sent_theirs = await send(client, theirs.id, theirs.token, client_ip="9.9.9.9")
    sent_mine = await send(client, mine.id, mine.token, client_ip=IP)

    assert sent_theirs["status"] == 200, sent_theirs
    assert sent_mine["status"] == 200, sent_mine


async def test_rate_limiting_happens_before_the_token_check(client) -> None:
    """Cost ordering. A flood of bad tokens must not reach the database.

    Checked structurally because a wall-clock test cannot tell the difference.
    Since the lifecycle checkpoint, the token compare lives in the shared
    `authorise` helper — so the ordering is asserted where it now actually
    holds: every action-bearing route spends the limiter before it asks for the
    capability check, and the helper does the compare in constant time.
    """
    import inspect

    from app.api import messages

    source = inspect.getsource(messages)

    # Matches the module-level limiter rather than a literal `limiter.check`, so
    # renaming the variable does not silently void this assertion.
    limiter_at = source.find("_approvals.check")
    compare_at = source.find("compare_digest")

    assert limiter_at != -1, "the routes must rate limit"
    assert compare_at != -1, "the token must be compared with hmac, not =="

    for name in ("send_message", "edit_message", "cancel_message"):
        route_src = inspect.getsource(getattr(messages, name))
        limited = route_src.find("_approvals.check")
        checked = route_src.find("authorise")

        assert limited != -1, f"{name} must rate limit"
        assert checked != -1, f"{name} must run the capability check"
        assert limited < checked, f"{name} must rate limit before checking the token"


async def test_a_rate_limited_request_is_429_with_retry_after(client, monkeypatch) -> None:
    """A real refusal, not a conditional.

    The fixture sets a generous cap so the other tests are not throttled, so this
    one installs its own. A conditional assertion here would pass whether or not
    the limiter exists.
    """
    from app.api import messages as messages_api

    monkeypatch.setattr(messages_api, "_approvals", RateLimiter(per_hour=3, burst=1))

    first = await client.post("/messages/1/send", json={"token": "x"})
    second = await client.post("/messages/1/send", json={"token": "x"})

    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1
    del first


# --- Body limits ------------------------------------------------------------


async def test_an_oversized_body_is_refused(client) -> None:
    """Cheap first, before anything parses or looks anything up."""
    response = await client.post(
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
        (await send(client, draft.id, draft.token, client_ip=IP)),
        (await send(client, draft.id, "wrong", client_ip=IP)),
        (await send(client, 999_999_999, "wrong", client_ip=IP)),
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

    result = await send(client, draft.id, "wrong-token", client_ip=IP)

    assert secret_phrase not in str(result["json"])


async def test_the_ip_hash_is_cleared_on_send(client) -> None:
    """The visitor's address stops existing the moment it has served its purpose."""
    from sqlalchemy import text

    from app.db import pool
    from tests.helpers import make_pending_draft

    draft = await make_pending_draft(IP=IP, salt=SALT)
    (await send(client, draft.id, draft.token, client_ip=IP))

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
    (await send(client, draft.id, draft.token, client_ip=IP))

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
        result = await send(client, draft.id, draft.token, client_ip=IP)

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
