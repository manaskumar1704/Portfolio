"""Phase 5 cannot send email. Structural assertions.

The tool `draft_message` is registered and reachable, and nothing in this phase
can turn a draft into a sent message. That is not an oversight — it is the
design — so it is worth a test rather than a comment. If these fail, phase 5 has
grown a send path that should not exist yet.
"""

import inspect
from pathlib import Path

import app.services.contact as contact
from app.main import app
from app.tools import registry

API_ROOT = Path(__file__).resolve().parents[1]


# --- Nothing in phase 5 can send -------------------------------------------


def test_no_resend_sdk_anywhere_in_the_project() -> None:
    """The dependency is not added until phase 6 needs it.

    This file is excluded: it necessarily contains the string it searches for.
    Everything else — app, ingest, tests — must be clean.
    """
    offenders = []
    for path in API_ROOT.rglob("*.py"):
        if ".venv" in path.parts or path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "import resend" in text or "from resend" in text:
            offenders.append(str(path.relative_to(API_ROOT)))

    assert offenders == []


def test_contact_service_makes_no_outbound_call() -> None:
    """No HTTP client, no socket, nothing that could reach a mail provider."""
    source = inspect.getsource(contact)

    for forbidden in ("httpx", "aiohttp", "smtplib", "socket", "requests", "resend"):
        assert forbidden not in source, f"contact.py references {forbidden}"


def test_no_send_route_exists() -> None:
    """Sending is POST /messages/{id}/send, and that is phase 6."""
    paths = {getattr(route, "path", "") for route in app.routes}

    assert not any("messages" in path for path in paths), paths


def test_no_tool_can_send() -> None:
    """Only four tools exist, and none of them sends."""
    names = {spec.name for spec in registry.specs()}

    assert names == {"echo", "search_portfolio", "get_github_repo", "draft_message"}
    assert not any("send" in name for name in names)


def test_create_draft_only_writes_a_pending_row() -> None:
    """The only status phase 5 can produce."""
    source = inspect.getsource(contact.create_draft)

    assert "'pending'" in source
    assert "'sent'" not in source


# --- The token never reaches the model --------------------------------------


def test_the_draft_confirmation_is_free_of_the_token() -> None:
    """`confirmation_for_model` is what the registry hands back to the loop."""
    from datetime import UTC, datetime, timedelta

    draft = contact.Draft(
        id=1,
        name="Ada",
        email="ada@example.com",
        body="Hi",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        token="LEAK-ME-IF-WRONG",
    )

    confirmation = contact.confirmation_for_model(draft)

    assert "LEAK-ME-IF-WRONG" not in confirmation
    assert "NOT sent" in confirmation


def test_the_approval_lookup_returns_no_token() -> None:
    """Phase 6 gets the row, not the capability."""
    assert "token" in inspect.signature(contact.get_draft_for_approval).parameters


# --- Phase 6's building blocks are in place ---------------------------------


def test_the_approval_lookup_checks_id_token_ip_and_expiry() -> None:
    """All four, in one query, so a partial match leaks nothing."""
    source = inspect.getsource(contact.get_draft_for_approval)

    for clause in (
        "approval_token_hash",
        "origin_ip",
        "status = 'pending'",
        "expires_at > now()",
    ):
        assert clause in source, clause


def test_the_status_enum_covers_what_phase6_will_write() -> None:
    """Otherwise phase 6 needs a migration to record what it did."""
    from app.db.models import MESSAGE_STATUSES

    assert set(MESSAGE_STATUSES) == {"pending", "sent", "expired", "failed"}
