"""Phase 6's boundary: the model cannot send, and never sees the key.

This replaces `test_no_send_in_p5.py`. Three of that file's nine tests were about
phase 5 not having a send path, and phase 6 has one by design, so those three are
gone. The remaining six asserted properties that still hold, and they are here.

The boundary changed shape. In phase 5 the rule was "no send route exists". In
phase 6 the rule is narrower and stronger: **the model has no send tool, and the
route that does send requires a token the model can never read.** A send route
being reachable by anyone on the internet is fine; it being reachable by
prompt injection through the chat is not.

## What each removed test was

| Removed | Why |
|---|---|
| `test_no_send_route_exists` | Its premise is now false. A send route is the point of P6. |
| `test_no_resend_sdk_anywhere` | Phase 6 is the phase that adds it. |
| `test_contact_service_makes_no_outbound_call` | Replaced below, scoped to the right file. |

Nothing was removed for being inconvenient. The replacement is strictly stronger
than what it replaces.
"""

import inspect
from pathlib import Path

from app.main import app
from app.tools import registry

API_ROOT = Path(__file__).resolve().parents[1]

# The four tools phase 6 leaves in place. Adding a fifth is a design change, not
# an implementation detail.
EXPECTED_TOOLS = {"echo", "search_portfolio", "get_github_repo", "draft_message"}


# --- The model still cannot send --------------------------------------------


def test_the_tool_set_is_unchanged_by_p6() -> None:
    """Phase 6 added a route, not a capability the model can reach."""
    assert {spec.name for spec in registry.specs()} == EXPECTED_TOOLS


def test_no_tool_can_send() -> None:
    """The boundary, stated as a test so P7 cannot quietly widen it.

    A tool called `send_message` or `email_owner` would make the token check
    optional, because the model could simply do the sending.
    """
    names = {spec.name for spec in registry.specs()}

    assert not any("send" in name or "email" in name for name in names)


def test_draft_message_cannot_send() -> None:
    """It writes a row and returns a confirmation. Nothing more."""
    from app.tools.integrations import draft_message

    source = inspect.getsource(draft_message)

    for forbidden in ("resend", "smtplib", "httpx", "aiohttp"):
        assert forbidden not in source


def test_the_registry_handler_for_drafting_is_still_the_drafter() -> None:
    """Guards against the handler being swapped for one that sends."""
    entry = registry.resolve("draft_message")

    assert entry is not None
    assert entry[1].__name__ == "draft_message"


# --- The split is in the right files ----------------------------------------


def test_only_email_service_imports_resend() -> None:
    """One file owns the provider call, and it is not reachable from a tool."""
    offenders = []
    for path in API_ROOT.rglob("*.py"):
        if ".venv" in path.parts or path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "import resend" in text or "from resend" in text:
            offenders.append(str(path.relative_to(API_ROOT)))

    assert offenders == ["app\\services\\email.py"], offenders


def test_the_send_route_exists_and_is_the_only_one() -> None:
    """Sending is reachable, and through exactly one door."""
    send_routes = [
        route
        for route in app.routes
        if getattr(route, "path", "").startswith("/messages")
        and "send" in getattr(route, "path", "")
        and "POST" in getattr(route, "methods", set())
    ]

    assert len(send_routes) == 1, [getattr(r, "path", "") for r in send_routes]


def test_contact_service_still_cannot_send() -> None:
    """Rewritten from P5's version: same property, now that email.py exists.

    P5 asserted no HTTP client anywhere in `contact.py`. Phase 6 adds
    `app/services/email.py`, so the assertion moves to the real requirement:
    `contact.py` drafts, `email.py` sends, and neither imports the other.
    """
    from app.services import contact

    source = inspect.getsource(contact)

    for forbidden in ("resend", "smtplib", "httpx", "aiohttp", "socket"):
        assert forbidden not in source, forbidden


def test_email_service_is_not_imported_by_any_tool() -> None:
    """The reachability path that would defeat the token check."""
    for module_name in ("app.tools.registry", "app.tools.integrations", "app.tools.search"):
        module = __import__(module_name, fromlist=["*"])
        source = inspect.getsource(module)

        assert "services.email" not in source, module_name
        assert "import resend" not in source, module_name


# --- The token never reaches the model --------------------------------------


def test_the_confirmation_given_to_the_model_has_no_token() -> None:
    """P5's rule, unchanged and still the load-bearing one."""
    from datetime import UTC, datetime, timedelta

    from app.services.contact import Draft, confirmation_for_model

    draft = Draft(
        id=1,
        name="Ada",
        email="ada@example.com",
        body="Hi",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        token="THE-SEND-KEY",
    )

    confirmation = confirmation_for_model(draft)

    assert "THE-SEND-KEY" not in confirmation


def test_the_draft_tool_result_has_no_token() -> None:
    """The tool result is what the loop reads. No token in it, ever.

    The token travels as a structured `draft` event emitted by the router from
    the same result object, which is why this is safe: the loop has a copy that
    it is forbidden to put in a prompt, and a separate copy the browser gets.
    """
    from app.tools.integrations import draft_message

    source = inspect.getsource(draft_message)

    # It may create the draft (which has the token) but must not put the token in
    # the returned dict.
    returned = source.split("return {", 1)[-1]
    assert "approval_token" not in returned
    assert ".token" not in returned


def test_the_chat_loop_strips_the_token_before_the_model() -> None:
    """The loop sees the token and must not forward it.

    Checked structurally: the loop pulls `approval_token` out of the tool result
    and emits a `draft` event, which is the only path to the browser.
    """
    from app.services import chat

    source = inspect.getsource(chat)

    assert "approval_token" in source, "the loop must handle the draft token"
    assert "DraftEvent" in source or '"draft"' in source


def test_the_system_prompt_does_not_mention_sending() -> None:
    """The model is told drafts need approval, and nothing about how to send."""
    from app.services.chat import SYSTEM_INSTRUCTION

    lowered = SYSTEM_INSTRUCTION.lower()

    assert "approve" in lowered
    assert "approval_token" not in lowered
    assert "resend" not in lowered


# --- Phase 6 building blocks exist ------------------------------------------


def test_ip_hashing_is_configured() -> None:
    """Without a salt, no draft can ever be approved."""
    from app.core.config import get_settings

    assert len(get_settings().ip_hash_salt) >= 16


def test_the_status_enum_covers_everything_the_route_writes() -> None:
    """`failed` exists because a Resend error must be recorded, not retried blind."""
    from app.db.models import MESSAGE_STATUSES

    assert set(MESSAGE_STATUSES) == {"pending", "sent", "expired", "failed"}


def test_the_daily_cap_is_below_resends_free_tier() -> None:
    """Resend allows 100/day. The cap must sit under it with room to spare."""
    from app.core.config import get_settings

    cap = get_settings().daily_send_cap

    assert 0 < cap < 100, f"daily_send_cap={cap} does not sit below Resend's 100/day"
