"""Two tool wrappers: live GitHub data, and drafting a message.

Thin on purpose. Each function validates, calls a service, and shapes the result.
The logic lives in `services/` so phase 7's MCP server can call the same
functions without going through a model at all.
"""

import re

import httpx
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services import contact as contact_service
from app.services import github as github_service
from app.services.github import GitHubError

log = get_logger(__name__)

GITHUB_DESCRIPTION = (
    "Live public data for one of this site's repositories: stars, forks, primary "
    "language, topics, last push date, and a short README excerpt. Use it when a "
    "question is about current popularity or recent activity. Static facts about "
    "what a project does are better answered by search_portfolio. Call it with no "
    "argument to get every repository on this site."
)

DRAFT_DESCRIPTION = (
    "Save a draft message from a visitor to the site owner. This does NOT send "
    "anything: the visitor reviews it in the chat interface and approves it, and "
    "only then is it emailed. Use it when a visitor asks to get in touch, leave "
    "their details, or send a message. You need their name, their email address, "
    "and what they want to say — ask for anything missing. After saving, tell them "
    "it is saved and waiting for their approval. Never say it has been sent."
)


class GetGithubRepoArgs(BaseModel):
    repo: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Repository name, 'owner/repo', or GitHub URL. Omit to list every "
            "repository on this site."
        ),
    )


class DraftMessageArgs(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=contact_service.MAX_NAME,
        description="The visitor's name.",
    )
    email: str = Field(
        min_length=3,
        max_length=contact_service.MAX_EMAIL,
        description="The visitor's email address, so the owner can reply.",
    )
    body: str = Field(
        min_length=1,
        max_length=contact_service.MAX_BODY,
        description="The message the visitor wants to send, in their own words.",
    )


async def get_github_repo(
    repo: str | None = None,
    origin_client: httpx.AsyncClient | None = None,
) -> dict:
    """Live repository data, trimmed to what a recruiter would ask about.

    `repo=None` returns every pinned repository, which is the answer to "what
    have you built" for a visitor who does not know the names.

    Errors come back as `{"error": "..."}` rather than raising, because the
    registry turns a raised exception into a generic string and these messages
    are written to be useful to the model.
    """
    from app.core.config import get_settings

    settings = get_settings()

    try:
        settings.require_github()
    except RuntimeError as exc:
        # Configuration, not a visitor error. Logged in full; the model is told
        # only that it is unavailable.
        log.error("github tool misconfigured: %s", exc)
        return {"error": "Repository data is not available on this site."}

    allowed = sorted(settings.allowed_github_repos())
    if not allowed:
        return {
            "error": "No repositories are configured on this site.",
            "hint": "Set GITHUB_PINS to a comma-separated list of repositories.",
        }

    if repo is None:
        client = origin_client or httpx.AsyncClient()
        owns_client = origin_client is None
        try:
            repos = []
            for full_name in allowed:
                try:
                    info = await github_service.fetch_repo(full_name, settings, client)
                except GitHubError as exc:
                    # One unreachable repository should not empty the whole list.
                    log.warning("repo %s unavailable: %s", full_name, exc)
                    continue
                repos.append(info.to_dict())
        finally:
            if owns_client:
                await client.aclose()

        return {"repositories": repos, "count": len(repos)}

    full_name = github_service.normalise_repo_name(repo, settings)
    if full_name is None:
        return {
            "error": "That repository is not one of this site's repositories.",
            "available": allowed,
        }

    cache = github_service.get_cache(settings)
    cached = cache.get(full_name)
    if cached is not None:
        return {**cached, "cached": True}

    try:
        info = await github_service.fetch_repo(full_name, settings, origin_client)
    except GitHubError as exc:
        log.info("github repo %s failed: %s", full_name, exc)
        payload = {"error": str(exc)}
        if exc.retry_after:
            payload["retry_after_seconds"] = exc.retry_after
        return payload

    result = info.to_dict()
    cache.set(full_name, result)
    return result


def _sanitise_name(value: str) -> str:
    """Names are for display, so strip anything that could render oddly."""
    return re.sub(r"[\r\n\t]", " ", value).strip()


async def draft_message(name: str, email: str, body: str, origin_ip: str = "") -> dict:
    """Save a draft. Does not send, and cannot.

    `origin_ip` is threaded in from the request rather than read from a global,
    so the MCP server in phase 7 can pass its own value and tests can pin it.
    """
    try:
        draft = await contact_service.create_draft(_sanitise_name(name), email, body, origin_ip)
    except contact_service.DraftError as exc:
        # The message is already written for a human, so it can go to the model
        # to relay verbatim.
        return {"error": str(exc)}

    return {
        "draft_id": draft.id,
        "status": "pending",
        "sent": False,
        "name": draft.name,
        "email": draft.email,
        "expires_at": draft.expires_at.isoformat(),
        "confirmation_for_you": contact_service.confirmation_for_model(draft),
    }
