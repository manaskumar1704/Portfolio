"""The two new tool wrappers, with no network and no database.

These assert the contract between the tools and the registry: the argument
schemas match the handlers, the errors come back as data rather than exceptions,
and neither tool can do anything the phase rules forbid.
"""

import pytest
from pydantic import ValidationError

from app.tools.integrations import (
    DraftMessageArgs,
    GetGithubRepoArgs,
    draft_message,
    get_github_repo,
)

# --- get_github_repo --------------------------------------------------------


def test_repo_is_optional() -> None:
    """Omitting it is the documented way to ask 'what have you built'."""
    assert GetGithubRepoArgs().repo is None


def test_repo_length_is_bounded() -> None:
    with pytest.raises(ValidationError):
        GetGithubRepoArgs(repo="x" * 300)


async def test_a_misconfigured_tool_reports_unavailable(monkeypatch) -> None:
    """Configuration, not a visitor error. The model gets a neutral message."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "github_token", "")
    monkeypatch.setattr(settings, "github_owner", "")

    result = await get_github_repo("alpha")

    assert "error" in result
    assert "not available" in result["error"]


async def test_no_pins_configured_is_reported(monkeypatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "github_token", "ghp_x")
    monkeypatch.setattr(settings, "github_owner", "testowner")
    monkeypatch.setattr(settings, "github_pins", [])

    result = await get_github_repo("alpha")

    assert "error" in result
    assert "No repositories are configured" in result["error"]


async def test_a_repo_outside_the_allowlist_lists_what_is_allowed(monkeypatch) -> None:
    """Telling the model the valid names is more useful than a flat refusal."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "github_token", "ghp_x")
    monkeypatch.setattr(settings, "github_owner", "testowner")
    monkeypatch.setattr(settings, "github_pins", ["alpha"])

    result = await get_github_repo("someoneelse/secret")

    assert "not one of this site's repositories" in result["error"]
    assert result["available"] == ["testowner/alpha"]


async def test_a_rate_limit_reaches_the_model_with_a_retry_hint(monkeypatch) -> None:
    """A 429 the visitor cannot act on is a bad answer; tell the model when to retry."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "github_token", "ghp_x")
    monkeypatch.setattr(settings, "github_owner", "testowner")
    monkeypatch.setattr(settings, "github_pins", ["alpha"])

    from app.services import github

    async def limited(*args, **kwargs):
        raise github.GitHubError("rate limit used up", status=403, retry_after=120)

    monkeypatch.setattr(github, "fetch_repo", limited)

    result = await get_github_repo("alpha")

    assert "rate limit" in result["error"]
    assert result["retry_after_seconds"] == 120


async def test_a_successful_fetch_is_cached(monkeypatch) -> None:
    """The second visitor asking about the same repo costs nothing."""
    from app.core.config import get_settings
    from app.services import github

    settings = get_settings()
    monkeypatch.setattr(settings, "github_token", "ghp_x")
    monkeypatch.setattr(settings, "github_owner", "testowner")
    monkeypatch.setattr(settings, "github_pins", ["alpha"])
    github.reset_cache()

    calls = 0

    async def fake_fetch(name, s, client=None):
        nonlocal calls
        calls += 1
        return github.RepoInfo(name, "d", 1, 0, "Python", [], "now", "u", None, "readme")

    monkeypatch.setattr(github, "fetch_repo", fake_fetch)

    first = await get_github_repo("alpha")
    second = await get_github_repo("alpha")

    assert calls == 1
    assert first.get("cached") is not True
    assert second.get("cached") is True
    github.reset_cache()


async def test_listing_every_repo_survives_one_failure(monkeypatch) -> None:
    """One unreachable repository should not empty the whole list."""
    from app.core.config import get_settings
    from app.services import github

    settings = get_settings()
    monkeypatch.setattr(settings, "github_token", "ghp_x")
    monkeypatch.setattr(settings, "github_owner", "testowner")
    monkeypatch.setattr(settings, "github_pins", ["alpha", "beta"])

    async def sometimes(name, s, client=None):
        if name.endswith("beta"):
            raise github.GitHubError("temporarily unavailable")
        return github.RepoInfo(name, "d", 1, 0, "Python", [], "now", "u", None, "readme")

    monkeypatch.setattr(github, "fetch_repo", sometimes)
    github.reset_cache()

    result = await get_github_repo(None)

    assert result["count"] == 1
    assert result["repositories"][0]["name"] == "testowner/alpha"
    github.reset_cache()


# --- draft_message ----------------------------------------------------------


def test_all_three_fields_are_required() -> None:
    """The model must supply a reply address or the owner cannot respond."""
    for missing in ("name", "email", "body"):
        kwargs = {"name": "Ada", "email": "ada@example.com", "body": "Hi"}
        kwargs.pop(missing)
        with pytest.raises(ValidationError):
            DraftMessageArgs(**kwargs)


def test_body_length_is_bounded() -> None:
    with pytest.raises(ValidationError):
        DraftMessageArgs(name="Ada", email="ada@example.com", body="x" * 5000)


async def test_an_invalid_email_is_reported_not_raised(monkeypatch) -> None:
    """The error must reach the model so it can ask for a correct address."""
    from app.services import contact as contact_service

    async def no_db(*args, **kwargs):
        # Same validation the real function does first, so the failure happens
        # before any database work.
        contact_service.validate_draft(args[0], args[1], args[2])

    monkeypatch.setattr(contact_service, "create_draft", no_db)

    result = await draft_message("Ada", "not-an-email", "Hi")

    assert "valid email" in result["error"]


async def test_a_name_with_newlines_is_flattened(monkeypatch) -> None:
    """A name is rendered in an email header; a newline there is injection."""
    seen = {}

    from app.services import contact as contact_service

    async def capture(name, email, body):
        seen["name"] = name
        raise contact_service.DraftError("stop here")

    monkeypatch.setattr(contact_service, "create_draft", capture)

    await draft_message("Ada\r\nBcc: victim@example.com", "ada@example.com", "Hi")

    assert "\n" not in seen["name"]
    assert "\r" not in seen["name"]


async def test_the_draft_tool_separates_the_token_from_the_prose(monkeypatch) -> None:
    """Rewritten for phase 6: the token is in the result now, and that is correct.

    In phase 5 the tool returned no token and the browser had no way to approve a
    message. Phase 6 puts it in the result so the chat loop can emit it as a
    structured `draft` event, and the loop strips it again before the model sees
    the same dict.

    So the property is not "the result has no token" — it is "the token is a
    field, not part of the prose the model reads". Asserting the former would
    assert the feature is broken; asserting that the token leaks into
    `confirmation_for_you` is the thing that would actually be a bug.
    """
    from datetime import UTC, datetime, timedelta

    from app.services import contact as contact_service

    draft = contact_service.Draft(
        id=7,
        name="Ada",
        email="ada@example.com",
        body="Hi",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        token="TOP-SECRET-TOKEN",
    )

    async def make(*args, **kwargs):
        return draft

    monkeypatch.setattr(contact_service, "create_draft", make)

    result = await draft_message("Ada", "ada@example.com", "Hi")

    assert result["status"] == "pending"
    assert result["sent"] is False

    # The loop pops this key and emits it as a `draft` event. Its presence is the
    # only way a browser ever learns the token.
    assert result["approval_token"] == "TOP-SECRET-TOKEN"

    # What the model actually reads.
    assert "TOP-SECRET-TOKEN" not in result["confirmation_for_you"]
    assert result["confirmation_for_you"] == contact_service.confirmation_for_model(draft)
