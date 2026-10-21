"""Search the portfolio corpus. The one RAG tool.

RAG is a tool rather than a step that always runs, and that is deliberate. The
corpus is tens of chunks; injecting all of it into every prompt wastes tokens and
actively hurts the questions that need no corpus at all — "send him a message"
needs no retrieval. As a tool, the model decides whether the corpus is relevant,
and the logs record how often it decided not to.

The handler is a thin wrapper. The retrieval itself lives in `services/rag.py` so
phase 7's MCP server can expose it without going through a model at all, and so
phase 8's evals can call it directly.
"""

import inspect

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services import rag

log = get_logger(__name__)


class SearchPortfolioArgs(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=500,
        description="A search query about the portfolio owner's work, skills, or history.",
    )
    limit: int = Field(
        default=rag.DEFAULT_LIMIT,
        ge=1,
        le=8,
        description="How many passages to return. Four is usually right.",
    )


async def search_portfolio(query: str, limit: int = rag.DEFAULT_LIMIT) -> dict:
    """Search the corpus and return passages with their source paths.

    Returns `found`, `sources` and `text` whether or not anything matched. The
    empty case is a normal outcome and says so explicitly, so the model reports
    "I don't know" instead of answering from whatever drifted past the distance
    threshold.
    """
    from app.core.config import get_settings

    settings = get_settings()
    results = await rag.search(query, settings, limit=limit)
    return rag.format_results(results)


async def call_search_portfolio(args: SearchPortfolioArgs) -> dict:
    """Registry entry point: validate, then run.

    Kept separate from `search_portfolio` so the function stays importable and
    callable by the MCP server with plain arguments, exactly as the chat path
    calls it. # ponytail: two entry points rather than one; collapse them if a
    third caller appears that needs neither shape.
    """
    return await search_portfolio(args.query, args.limit)


def is_async_handler(handler) -> bool:
    """Whether a handler needs awaiting.

    Retrieval is async because it embeds a query on the ONNX model, and GitHub
    and email in phase 5 will be too. Checking once here is cheaper than making
    every handler async for the sake of `echo`, which is sync and stays sync
    because it is a test stub.
    """
    return inspect.iscoroutinefunction(handler)
