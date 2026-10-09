"""Tool registry: the allowlist.

Only what is registered here can ever be called. The model picks a name from
this set; it cannot invent one. That is the whole security boundary for
tool-calling, and it is why this is a module-level dict rather than anything
derived from the service layer at runtime.

Each entry pairs a `ToolSpec` (what the model sees) with a handler (what
actually runs), plus the Pydantic model that validates the model's arguments.

The handlers take plain arguments and return JSON-serialisable data. They do not
know they are being called by a model, which is what lets phase 7's MCP server
import the same functions directly.

`draft_message` is registered here and still cannot send email. It writes a
pending row; sending is a phase-6 HTTP route with its own token check. Keeping
that split is the point: if sending were a tool, a prompt-injected visitor could
reach it through the model.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.llm import ToolSpec
from app.tools.integrations import (
    DRAFT_DESCRIPTION,
    GITHUB_DESCRIPTION,
    DraftMessageArgs,
    GetGithubRepoArgs,
    draft_message,
    get_github_repo,
)
from app.tools.search import SearchPortfolioArgs, search_portfolio

log = get_logger(__name__)


class EchoArgs(BaseModel):
    """Arguments for the phase-3 stub tool."""

    text: str = Field(min_length=1, max_length=500)


def echo(text: str) -> dict[str, str]:
    """Returns its input. Proves the loop works end to end before phase 4."""
    return {"echoed": text}


SEARCH_DESCRIPTION = (
    "Search the portfolio owner's résumé, projects, certifications, and profile "
    "snapshots. Use this for any question about their work history, skills, "
    "employers, dates, or projects. Returns passages with the source file each "
    "came from, so you can cite them. Returns nothing when the corpus has no "
    "match — in that case say you do not know rather than guessing."
)

_REGISTRY: dict[str, tuple[ToolSpec, Any, type[BaseModel]]] = {
    "echo": (
        ToolSpec(
            name="echo",
            description="Echo a short string back. Used to demonstrate tool calling.",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string", "description": "The text to echo."}},
                "required": ["text"],
            },
        ),
        echo,
        EchoArgs,
    ),
    "search_portfolio": (
        ToolSpec(
            name="search_portfolio",
            description=SEARCH_DESCRIPTION,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A search query, e.g. 'which company did they "
                        "work at before Lantern Analytics'.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "How many passages to return. Defaults to 4.",
                        "minimum": 1,
                        "maximum": 8,
                    },
                },
                "required": ["query"],
            },
        ),
        search_portfolio,
        SearchPortfolioArgs,
    ),
    "get_github_repo": (
        ToolSpec(
            name="get_github_repo",
            description=GITHUB_DESCRIPTION,
            parameters={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository name, 'owner/repo', or URL. "
                        "Omit to get every repository on this site.",
                        "maxLength": 200,
                    },
                },
                # Nothing required: omitting repo is the documented way to ask
                # "what have you built". Requiring it would make the model
                # invent a name.
                "required": [],
            },
        ),
        get_github_repo,
        GetGithubRepoArgs,
    ),
    "draft_message": (
        ToolSpec(
            name="draft_message",
            description=DRAFT_DESCRIPTION,
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The visitor's name.",
                        "maxLength": 200,
                    },
                    "email": {
                        "type": "string",
                        "description": "The visitor's email address, so the owner can reply.",
                        "maxLength": 320,
                    },
                    "body": {
                        "type": "string",
                        "description": "The message, in the visitor's own words.",
                        "maxLength": 4000,
                    },
                },
                "required": ["name", "email", "body"],
            },
        ),
        draft_message,
        DraftMessageArgs,
    ),
}


def specs() -> list[ToolSpec]:
    """The tool schemas to send to the model."""
    return [spec for spec, _, _ in _REGISTRY.values()]


def resolve(name: str) -> tuple[ToolSpec, Any, type[BaseModel]] | None:
    """Look up a tool. None means the model asked for something not registered."""
    return _REGISTRY.get(name)


async def call(name: str, arguments: dict[str, Any]) -> tuple[Any, str | None]:
    """Run a registered tool.

    Returns `(result, error_message)`. Never raises: a tool that throws must not
    take down the stream, and the error goes back to the model as a tool result
    so it can recover or explain itself. The message is written for the model,
    so it never includes a traceback.

    Async because retrieval embeds a query on the ONNX model and phase 5's tools
    will make network calls. The sync `echo` stub is awaited-or-not depending on
    what it is, which costs one `iscoroutinefunction` check.
    """
    import inspect

    entry = resolve(name)
    if entry is None:
        log.warning("model asked for unregistered tool %r", name)
        return None, f"no such tool: {name}"

    spec, handler, args_model = entry

    from app.services.llm import validate_arguments

    complaint = validate_arguments(args_model, arguments)
    if complaint is not None:
        log.info("tool %s rejected arguments: %s", name, complaint)
        return None, complaint

    try:
        if inspect.iscoroutinefunction(handler):
            return await handler(**arguments), None
        return handler(**arguments), None
    except Exception as exc:
        # Logged with the real detail, reported to the model without it. A
        # traceback in a visitor-facing answer is an information leak.
        log.exception("tool %s failed", name)
        return None, f"{type(exc).__name__}: the tool could not complete"
