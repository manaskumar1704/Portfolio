"""Live public repository data from the GitHub REST API.

This is the one capability whose data genuinely cannot come from the corpus: star
counts, last push and README contents change, and an answer built from a
retrieved chunk would be wrong within a day. Static facts about a project (what
it does, its stack) belong in `corpus/projects.md`. This returns only what moves.

## Why an allowlist

`get_github_repo` is reachable by anyone who loads the page. Without a boundary,
a visitor could point it at any repository and spend the token's rate limit, or
use it as an SSRF-adjacent probe into private repos the token can read. So the
tool only serves repositories under `GITHUB_OWNER`, and `GITHUB_PINS` narrows
that further to the repositories worth demoing.

The boundary is a full-string match on `owner/repo`, not a substring. A prefix
match would let `manas-dev/portfolio-evil` through on the strength of sharing a
prefix with an allowed `manas-dev/portfolio`.

## Why a cache

GitHub's authenticated rate limit is generous, but it is per token and shared by
every visitor. Star counts do not change by the minute, so a 15-minute TTL means
the second recruiter asking about the same repository costs nothing.

## Status codes, and what the model is told

| Status | Meaning | What the model gets |
|---|---|---|
| 404 | not in the allowlist, or does not exist | "not available", never "not found" |
| 403 + `rate limit` | token quota spent | "temporarily unavailable, try later" |
| 403 otherwise | token lacks access | "not available" |
| 5xx | GitHub is down | "temporarily unavailable" |

404 and "does not exist" are reported identically on purpose. Distinguishing them
turns the tool into an oracle for probing which repositories exist under an
account.

## The README is untrusted

A README is third-party text that reaches the model inside a prompt. It is
returned as a labelled data field, capped, and stripped of anything that looks
like an instruction to the model. It is never concatenated into a system prompt
and never treated as a tool call.
"""

import base64
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

API_ROOT = "https://api.github.com"

# Enough for a recruiter to see what a repo is. A longer excerpt is mostly badges
# and installation instructions, which is prompt cost for nothing.
README_MAX_CHARS = 1200

# Markdown images and badges are noise here and burn the cap quickly.
_IMAGES = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_HTML_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
_LINK_TARGET = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_HEADING_MARKS = re.compile(r"^#{1,6}\s*", re.MULTILINE)

# Phrases that are instructions to a model rather than documentation. Not a
# security boundary — the model could be talked into anything by a clever README
# — but it removes the obvious accidental case, and the cap does the real work.
_INSTRUCTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"you\s+are\s+now\s+", re.I),
    re.compile(r"(call|invoke|use)\s+the\s+\w+\s+tool", re.I),
    re.compile(r"<\|.*?\|>", re.DOTALL),
)


class GitHubError(RuntimeError):
    """A GitHub call failed. Carries a message written for the model."""

    def __init__(self, message: str, *, status: int | None = None, retry_after: int | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


@dataclass
class _CacheEntry:
    value: dict[str, Any]
    expires_at: float


@dataclass
class RepoCache:
    """A tiny TTL cache. Deliberately not Redis.

    Render free runs one instance, so a process-local dict is the whole story. A
    shared store would add a dependency and a second free-tier limit to solve a
    problem that does not exist. This resets on spin-down, which is fine: a cold
    container has an empty cache anyway.

    # ponytail: unbounded dict, no eviction. Add an LRU bound when this is run
    # for months without restarting and the repo list grows into the hundreds.
    """

    ttl: float
    _entries: dict[str, _CacheEntry] = field(default_factory=dict)

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.monotonic():
            del self._entries[key]
            return None
        return entry.value

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._entries[key] = _CacheEntry(value=value, expires_at=time.monotonic() + self.ttl)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


def clean_readme(markdown: str, limit: int = README_MAX_CHARS) -> str:
    """Reduce a README to plain prose, capped.

    Three things are removed and one is redacted. Images and badges take the
    budget and say nothing. Link targets are noise; the link text is the content.
    Heading marks are dropped because the chunk's own heading is what the model
    needs, and a README's `#` hierarchy competes with it.

    Instruction-shaped text is replaced with a marker rather than removed, so the
    model can see that something was there and does not silently receive a
    document with a suspicious gap.
    """
    text = _HTML_COMMENTS.sub("", markdown)
    text = _IMAGES.sub("", text)
    text = _LINK_TARGET.sub(r"\1", text)
    text = _HEADING_MARKS.sub("", text)

    for pattern in _INSTRUCTION_PATTERNS:
        text = pattern.sub("[redacted: instruction-shaped text in a third-party README]", text)

    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) <= limit:
        return text

    # Cut on a line boundary where one is close, so the excerpt does not end
    # mid-table-row.
    cut = text[:limit]
    newline = cut.rfind("\n", limit // 2)
    if newline != -1:
        cut = cut[:newline]
    return f"{cut.rstrip()}\n[truncated, {len(text)} characters total]"


def _decode_readme(payload: dict[str, Any]) -> str:
    """GitHub returns the README base64-encoded; content can also be raw."""
    if payload.get("encoding") == "base64" and payload.get("content"):
        try:
            return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return ""
    return payload.get("content") or ""


@dataclass(frozen=True)
class RepoInfo:
    """The trimmed shape the model sees. Not the raw API payload.

    The raw repository object is ~40 fields, most of them irrelevant to a
    question about someone's work, and every one of them is prompt cost on a
    free tier.
    """

    name: str
    description: str
    stars: int
    forks: int
    language: str
    topics: list[str]
    last_push: str
    url: str
    homepage: str | None
    readme_excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "stars": self.stars,
            "forks": self.forks,
            "language": self.language,
            "topics": self.topics,
            "last_push": self.last_push,
            "url": self.url,
            "homepage": self.homepage,
            "readme_excerpt": self.readme_excerpt,
            "readme_is_untrusted_data": True,
        }


def normalise_repo_name(repo: str | None, settings: Settings) -> str | None:
    """Normalise a model-supplied repo name, or None if it is not allowed.

    Accepts `repo`, `owner/repo`, and the GitHub URL for either. Everything is
    lowercased and stripped of a leading slash so a URL from a search result
    matches a pinned name.
    """
    if not repo:
        return None

    candidate = repo.strip().lower()
    # Strip a full URL, or a bare `github.com/...` left over from a search result
    # with the scheme stripped. The scheme is optional because a model that pastes
    # `github.com/owner/repo` means the same thing as one that pastes the URL.
    candidate = re.sub(r"^(https?://)?(www\.)?github\.com/", "", candidate)
    candidate = candidate.rstrip("/")
    if candidate.endswith(".git"):
        candidate = candidate[: -len(".git")]
    if candidate.startswith("/"):
        candidate = candidate[1:]

    if "/" not in candidate:
        candidate = f"{settings.github_owner.lower()}/{candidate}"

    allowed = settings.allowed_github_repos()
    return candidate if candidate in allowed else None


def _headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "portfolio-api",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


async def _get(client: httpx.AsyncClient, settings: Settings, path: str) -> dict[str, Any]:
    """One GET, with every failure mode translated into a model-readable message."""
    timeout = httpx.Timeout(settings.github_timeout_seconds, connect=3.0)
    try:
        response = await client.get(
            f"{API_ROOT}{path}", headers=_headers(settings), timeout=timeout
        )
    except httpx.TimeoutException as exc:
        raise GitHubError("GitHub did not respond in time. Try again shortly.") from exc
    except httpx.HTTPError as exc:
        # Never include the URL: a token in a query string would end up in the
        # model-visible message and in the logs.
        raise GitHubError("Could not reach GitHub just now.") from exc

    if response.status_code == 200:
        return response.json()

    if response.status_code == 404:
        # Indistinguishable from "not on the allowlist", on purpose.
        raise GitHubError("That repository is not available on this site.", status=404)

    if response.status_code == 403:
        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining == "0" or "rate limit" in response.text.lower():
            reset = response.headers.get("x-ratelimit-reset")
            retry_after = None
            if reset and reset.isdigit():
                retry_after = max(1, int(reset) - int(time.time()))
            raise GitHubError(
                "GitHub's rate limit for this site is used up. Try again later.",
                status=403,
                retry_after=retry_after,
            )
        raise GitHubError("That repository is not available on this site.", status=403)

    if response.status_code >= 500:
        raise GitHubError(
            "GitHub is having problems. Try again shortly.", status=response.status_code
        )

    raise GitHubError(
        f"GitHub returned an unexpected status ({response.status_code}).",
        status=response.status_code,
    )


async def fetch_repo(
    full_name: str,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> RepoInfo:
    """Fetch one repository. Raises `GitHubError` with a model-readable message."""
    owned_by_us = full_name.split("/")[0] == settings.github_owner.lower()
    if not owned_by_us:
        raise GitHubError("That repository is not available on this site.", status=403)

    owns_client = client is None
    http = client or httpx.AsyncClient()
    try:
        payload = await _get(http, settings, f"/repos/{full_name}")
        try:
            readme_payload = await _get(http, settings, f"/repos/{full_name}/readme")
        except GitHubError as exc:
            if exc.status != 404:
                raise
            # A project can simply have no README. That is not the same as
            # "this repository is not on the allowlist"; the repo still lists.
            readme_payload = {}
    finally:
        if owns_client:
            await http.aclose()

    return RepoInfo(
        name=payload.get("full_name") or full_name,
        description=(payload.get("description") or "").strip() or "No description provided.",
        stars=payload.get("stargazers_count") or 0,
        forks=payload.get("forks_count") or 0,
        language=payload.get("language") or "Unknown",
        topics=list(payload.get("topics") or [])[:10],
        last_push=payload.get("pushed_at") or "unknown",
        url=payload.get("html_url") or "",
        homepage=payload.get("homepage") or None,
        readme_excerpt=clean_readme(_decode_readme(readme_payload)),
    )


_cache = RepoCache(ttl=900.0)


def get_cache(settings: Settings) -> RepoCache:
    """The shared cache, with the TTL from settings applied on first use."""
    if _cache.ttl != settings.github_cache_ttl:
        _cache.ttl = float(settings.github_cache_ttl)
    return _cache


def reset_cache() -> None:
    """Clear the cache. Tests use this."""
    _cache.clear()
