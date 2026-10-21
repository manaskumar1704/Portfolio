"""The search tool, without a database.

What is worth checking here is the argument contract and the shape of the return,
since those are what the model sees. The ranking itself is covered by
`test_rag.py` against the live database.
"""

import pytest
from pydantic import ValidationError

from app.tools.search import SearchPortfolioArgs, is_async_handler, search_portfolio


def test_arguments_are_validated() -> None:
    """A model that sends an empty or one-character query gets a complaint.

    Two characters is the floor: a single letter is never a real question, and
    embedding it would return arbitrary neighbours from a 20-chunk corpus.
    """
    with pytest.raises(ValidationError):
        SearchPortfolioArgs(query="")
    with pytest.raises(ValidationError):
        SearchPortfolioArgs(query="x")


def test_limit_is_bounded() -> None:
    """Eight passages is already more context than the system prompt wants."""
    assert SearchPortfolioArgs(query="resume", limit=8).limit == 8

    with pytest.raises(ValidationError):
        SearchPortfolioArgs(query="resume", limit=0)
    with pytest.raises(ValidationError):
        SearchPortfolioArgs(query="resume", limit=9)


def test_limit_defaults_to_four() -> None:
    from app.services import rag

    assert SearchPortfolioArgs(query="anything").limit == rag.DEFAULT_LIMIT


def test_search_is_an_async_handler() -> None:
    """Retrieval embeds a query on the ONNX model, so it must be awaited."""
    assert is_async_handler(search_portfolio) is True


def test_echo_is_not_an_async_handler() -> None:
    """The sync stub is why the registry checks at all."""
    from app.tools.registry import echo

    assert is_async_handler(echo) is False


async def test_search_tool_is_registered() -> None:
    """A tool the model can see but the registry cannot run is a dead tool."""
    from app.tools.registry import resolve, specs

    names = [spec.name for spec in specs()]
    assert "search_portfolio" in names
    assert resolve("search_portfolio") is not None


def test_search_description_tells_the_model_when_not_to_guess() -> None:
    """The description is the only place the model learns the abstention rule."""
    from app.tools.registry import resolve

    spec, _, _ = resolve("search_portfolio")

    assert "do not know" in spec.description.lower()
    assert "cite" in spec.description.lower() or "source" in spec.description.lower()


def test_search_schema_matches_the_handler_signature() -> None:
    """The JSON Schema and the Pydantic model must describe the same thing.

    They are written separately — one goes to the provider, one validates — so
    they can drift. A schema requiring `limit` while the model defaults it is the
    kind of drift that shows up as a model inventing arguments.
    """
    from app.tools.registry import resolve

    spec, _, args_model = resolve("search_portfolio")

    schema_props = set(spec.parameters["properties"])
    model_fields = set(args_model.model_fields)

    assert schema_props == model_fields
    assert spec.parameters["required"] == ["query"]
