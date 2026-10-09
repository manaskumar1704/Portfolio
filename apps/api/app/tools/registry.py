"""Tool registry: the allowlist.

Only what is registered here can ever be called. The model picks a name from
this set; it cannot invent one. That is the whole security boundary for
tool-calling, and it is why this is a module-level dict rather than anything
derived from the service layer at runtime.

Each entry pairs a `ToolSpec` (what the model sees) with a handler (what
actually runs). Phase 3 ships one stub. Phases 4 and 5 replace it with
`search_portfolio`, `get_github_repo` and `draft_message`.

The handlers take plain arguments and return JSON-serialisable data. They do not
know they are being called by a model, which is what lets phase 7's MCP server
import the same functions directly.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.llm import ToolSpec

log = get_logger(__name__)


class EchoArgs(BaseModel):
    """Arguments for the phase-3 stub tool."""

    text: str = Field(min_length=1, max_length=500)


def echo(text: str) -> dict[str, str]:
    """Returns its input. Proves the loop works end to end before phase 4."""
    return {"echoed": text}


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
}


def specs() -> list[ToolSpec]:
    """The tool schemas to send to the model."""
    return [spec for spec, _, _ in _REGISTRY.values()]


def resolve(name: str) -> tuple[ToolSpec, Any, type[BaseModel]] | None:
    """Look up a tool. None means the model asked for something not registered."""
    return _REGISTRY.get(name)


def call(name: str, arguments: dict[str, Any]) -> tuple[Any, str | None]:
    """Run a registered tool.

    Returns `(result, error_message)`. Never raises: a tool that throws must not
    take down the stream, and the error goes back to the model as a tool result
    so it can recover or explain itself. The message is written for the model,
    so it never includes a traceback.
    """
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
        return handler(**arguments), None
    except Exception as exc:
        # Logged with the real detail, reported to the model without it. A
        # traceback in a visitor-facing answer is an information leak.
        log.exception("tool %s failed", name)
        return None, f"{type(exc).__name__}: the tool could not complete"
