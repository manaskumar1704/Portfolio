"""Live GitHub. Marked `slow`, opt in with -m slow.

The mock-based tests assert behaviour. This one asserts that GitHub still agrees
with those assumptions — that the auth header is accepted, that the fields we
read exist, and that the allowlist contains something real to fetch.

Cost is one request against a real token, so it is not in the default run.
"""

import httpx
import pytest

from app.core.config import get_settings
from app.services import github
from app.services.github import GitHubError

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not get_settings().github_token or not get_settings().github_owner,
        reason="GITHUB_TOKEN or GITHUB_OWNER not set",
    ),
]


async def test_the_allowlist_is_not_empty() -> None:
    """Nothing to test if no repo is pinned."""
    assert get_settings().allowed_github_repos()


async def test_a_pinned_repo_fetches_for_real() -> None:
    settings = get_settings()
    allowed = sorted(settings.allowed_github_repos())
    assert allowed, "set GITHUB_PINS to a repo under GITHUB_OWNER"

    async with httpx.AsyncClient() as client:
        info = await github.fetch_repo(allowed[0], settings, client)

    assert info.name
    assert info.stars >= 0
    # A trimmed shape, not the raw payload: the raw repository object is ~40
    # fields and every one of them is prompt cost.
    assert set(info.to_dict()) == {
        "name",
        "description",
        "stars",
        "forks",
        "language",
        "topics",
        "last_push",
        "url",
        "readme_excerpt",
        "homepage",
        "readme_is_untrusted_data",
    }


async def test_a_private_repo_is_refused_rather_than_leaked() -> None:
    """The allowlist must hold even when the token can read more."""
    settings = get_settings()
    other = f"{settings.github_owner}-definitely-not-a-real-org-xyz/secret"

    with pytest.raises(GitHubError, match="not available"):
        await github.fetch_repo(other, settings)


async def test_the_readme_is_cleaned_not_returned_raw() -> None:
    """Whatever GitHub returns, the model gets plain prose."""
    settings = get_settings()
    allowed = sorted(settings.allowed_github_repos())
    if not allowed:
        pytest.skip("no pinned repo")

    async with httpx.AsyncClient() as client:
        info = await github.fetch_repo(allowed[0], settings, client)

    excerpt = info.readme_excerpt
    assert "shields.io" not in excerpt
    assert len(excerpt) <= github.README_MAX_CHARS + 120
