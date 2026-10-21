"""The provider adapters, with no network.

What is worth checking without a live key is the translation in both directions:
conversation to provider shape, and provider shape to our vocabulary. A bug there
does not crash — it produces a subtly wrong conversation, which is worse.
"""

import pytest

from app.services.llm import (
    ChatMessage,
    GeminiClient,
    GroqClient,
    ToolResult,
    ToolSpec,
    validate_arguments,
)
from app.tools.registry import EchoArgs

TOOL = ToolSpec(
    name="echo",
    description="Echo.",
    parameters={"type": "object", "properties": {"text": {"type": "string"}}},
)


def gemini() -> GeminiClient:
    from app.core.config import get_settings

    settings = get_settings()
    settings.gemini_api_key = settings.gemini_api_key or "test-key"
    return GeminiClient(settings)


def test_gemini_input_uses_content_parts() -> None:
    """`content` must be a list of parts, not a bare string.

    The SDK types `UserInputStep.content` as `List[ContentParam]`. A string
    there fails pydantic validation locally, before any request is made.
    """
    steps = gemini()._to_input([ChatMessage(role="user", text="hello")])

    assert steps == [{"type": "user_input", "content": [{"type": "text", "text": "hello"}]}]


def test_gemini_tool_uses_the_function_shape() -> None:
    tool = gemini()._to_sdk_tool(TOOL)
    assert tool["type"] == "function"
    assert tool["name"] == "echo"
    assert tool["parameters"]["type"] == "object"


def test_gemini_tool_result_is_a_content_list() -> None:
    """A bare value here is the same class of bug as the input case."""
    step = gemini()._to_result_step(ToolResult(call_id="c1", name="echo", result={"a": 1}))

    assert step["type"] == "function_result"
    assert step["call_id"] == "c1"
    assert isinstance(step["result"], list)
    assert step["result"][0]["type"] == "text"
    assert step["result"][0]["text"] == '{"a": 1}'


def test_tool_failure_is_sent_as_data_not_an_exception() -> None:
    """The model has to read an error to recover from one."""
    step = gemini()._to_result_step(
        ToolResult(call_id="c1", name="echo", result=None, ok=False, error="invalid arguments")
    )

    assert '"error"' in step["result"][0]["text"]
    assert "invalid arguments" in step["result"][0]["text"]


def test_groq_tool_uses_the_openai_shape() -> None:
    tool = GroqClient._to_openai_tool(TOOL)
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "echo"


def test_validate_arguments_returns_none_when_valid() -> None:
    assert validate_arguments(EchoArgs, {"text": "hi"}) is None


def test_validate_arguments_describes_the_problem() -> None:
    """The complaint goes back to the model, so it has to name the field."""
    complaint = validate_arguments(EchoArgs, {})
    assert complaint is not None
    assert "text" in complaint


def test_validate_arguments_catches_the_wrong_type() -> None:
    assert validate_arguments(EchoArgs, {"text": 123}) is not None


@pytest.mark.parametrize("provider", ["gemini", "groq", "", "openai"])
def test_unknown_provider_is_rejected(provider: str) -> None:
    """A silent fallback would evaluate a different model than you think."""
    from app.core.config import get_settings
    from app.services.llm import build_llm_client

    settings = get_settings()
    settings.llm_provider = provider
    settings.gemini_api_key = "x"
    settings.groq_api_key = "x"

    if provider in ("gemini", "groq"):
        assert build_llm_client(settings) is not None
    else:
        with pytest.raises(ValueError):
            build_llm_client(settings)


def test_llm_api_key_follows_the_provider() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    settings.gemini_api_key = "gem"
    settings.groq_api_key = "gro"

    settings.llm_provider = "gemini"
    assert settings.llm_api_key == "gem"

    settings.llm_provider = "groq"
    assert settings.llm_api_key == "gro"
