"""The LLMClient interface, and the two provider implementations.

One interface, two adapters. The chat loop in `chat.py` is written against this
and nothing else, so swapping providers is an environment variable rather than
an edit to the loop.

## Why Gemini is primary

`gemini-3.5-flash-lite` on the free tier, verified against the live API:
1M input / 64k output tokens, and native `functionCall` support. It is the
cheapest and fastest option that does tool calling properly, and the whole
demo is a streaming chat UI, where time-to-first-token is the product.

Groq stays as the fallback for 429s. Its limits are per-organization and its
model names carry a provider prefix, so it is not a drop-in string swap — hence
two adapters and not one parameter.

## The shape of a tool loop, as the API actually allows it

This is the part worth knowing, because it is not what the docs imply.

A tool loop needs the model to say "call this function", the application to run
it, and the result to go back to the model. Gemini's Interactions API will only
accept a function result if it arrives on an interaction that already recorded
the call. Replaying the whole conversation from scratch with a synthetic
`function_call` step returns `400 invalid_request` — verified, not assumed.

So a turn is stateful: `stream()` takes a `previous_interaction_id` and returns
both the text and the id to use for the next leg. The loop keeps that id in
memory for the life of one request and forgets it afterwards. Nothing is
persisted, which is what `docs/decisions/0001` promised.

The alternative — replaying history as plain `user_input` steps — does work,
and is what a multi-turn conversation uses. Only the function-result leg needs
the id. Both paths are implemented and both are tested.

**Store policy.** Interactions are stored by default: 55 days on paid tiers, one
day on free. Setting `store=False` would opt out, but it also disables
`previous_interaction_id`, which is the mechanism the tool loop depends on.
Storing for one day is the cost of using the provider's own state machine, and
recruiters are already talking to a third-party model about public résumé data.
Logged as a decision rather than hidden.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

# Hard stop on the tool loop. Four legs is generous for two tools; without it a
# model that keeps calling the same tool loops until the request times out.
MAX_TOOL_ITERATIONS = 4


# --- The vocabulary the loop speaks -----------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    """A function the model is allowed to call.

    `parameters` is a JSON Schema object, verbatim. The loop never inspects it;
    only the provider does.
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})


@dataclass(frozen=True)
class ToolCall:
    """The model asking for a tool to run."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """What the tool returned, on its way back to the model."""

    call_id: str
    name: str
    result: Any
    ok: bool = True
    # Shown to the visitor. Never a traceback.
    error: str | None = None


@dataclass
class TurnResult:
    """One leg of a turn: the streamed text plus what comes next.

    `interaction_id` is the handle the next leg needs. It is `None` when the
    provider has no such concept, which is why the loop treats it as optional.
    """

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    interaction_id: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMClient(Protocol):
    """What the chat loop needs from a provider, and nothing more."""

    async def stream(
        self,
        *,
        messages: Sequence["ChatMessage"],
        tools: Sequence[ToolSpec],
        system_instruction: str,
        previous_interaction_id: str | None = None,
        tool_results: Sequence[ToolResult] = (),
    ) -> AsyncIterator[TurnResult]:
        """Stream one leg. Yields exactly once, at the end of the leg.

        An async iterator rather than a plain coroutine because the caller needs
        to emit tokens as they arrive. The final `TurnResult` carries the
        accumulated text, so the router never has to accumulate it itself.

        `tool_results` is non-empty only on the legs that follow a tool call, and
        `previous_interaction_id` is set on those same legs. How the two combine
        is the one place the providers genuinely differ.
        """
        ...


@dataclass(frozen=True)
class ChatMessage:
    """One turn of conversation, in provider-neutral terms."""

    role: str  # "user" or "bot"; "system" is passed separately
    text: str


# --- Gemini -----------------------------------------------------------------


class GeminiClient:
    """Adapter for Google's Interactions API via the `google-genai` SDK."""

    def __init__(self, settings: Settings) -> None:
        from google import genai

        self._model = settings.gemini_model
        self._client = genai.Client(api_key=settings.gemini_api_key)
        log.info("gemini client ready", extra={"model": self._model})

    def _to_sdk_tool(self, spec: ToolSpec) -> dict[str, Any]:
        return {
            "type": "function",
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        }

    def _to_input(self, messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
        """Flatten the conversation into `user_input` steps.

        `content` is a list of content parts, not a bare string. The SDK's type
        for `UserInputStep.content` is `List[ContentParam]`, and passing a string
        there fails validation locally before a request is ever made.
        """
        return [
            {
                "type": "user_input",
                "content": [{"type": "text", "text": message.text}],
            }
            for message in messages
        ]

    async def stream(
        self,
        *,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        system_instruction: str,
        previous_interaction_id: str | None = None,
        tool_results: Sequence[ToolResult] = (),
    ) -> AsyncIterator[TurnResult]:
        def run() -> TurnResult:
            kwargs: dict[str, Any] = {
                "model": self._model,
                "system_instruction": system_instruction,
                "tools": [self._to_sdk_tool(spec) for spec in tools] or None,
            }

            if previous_interaction_id is not None:
                # Leg two onwards. The interaction already holds the
                # user_input steps and the function_call; only the results go on.
                # Replaying the conversation instead returns 400, which is why
                # `messages` is ignored on this path.
                kwargs["input"] = [self._to_result_step(r) for r in tool_results]
                kwargs["previous_interaction_id"] = previous_interaction_id
            else:
                kwargs["input"] = self._to_input(messages)

            interaction = self._client.interactions.create(**kwargs)

            turn = TurnResult(interaction_id=interaction.id)
            for step in interaction.steps:
                if step.type == "function_call":
                    turn.tool_calls.append(
                        ToolCall(
                            id=step.id or "",
                            name=step.name or "",
                            arguments=dict(step.arguments or {}),
                        )
                    )
            turn.text = interaction.output_text or ""
            usage = interaction.usage
            if usage:
                turn.prompt_tokens = getattr(usage, "total_input_tokens", 0) or 0
                turn.completion_tokens = getattr(usage, "total_output_tokens", 0) or 0
            return turn

        # The SDK is synchronous and blocking. Running it in a worker thread is
        # what keeps one slow provider call from stalling every other visitor's
        # event loop.
        yield await asyncio.to_thread(run)

    @staticmethod
    def _to_result_step(result: ToolResult) -> dict[str, Any]:
        """A tool result as the API wants it.

        `result` is a list of content parts, not a bare value, and a failure is
        reported inside that content rather than as an exception: the model has
        to read the error to recover from it.
        """
        if result.ok:
            body: Any = result.result
        else:
            body = {"error": result.error or "tool failed"}
        return {
            "type": "function_result",
            "call_id": result.call_id,
            "name": result.name,
            "result": [{"type": "text", "text": json.dumps(body)}],
        }


# --- Groq -------------------------------------------------------------------


class GroqClient:
    """Fallback adapter for Groq's OpenAI-compatible endpoint.

    Kept thin and kept correct about the one thing that differs from Gemini:
    Groq's tool results are plain messages in the conversation, so there is no
    interaction id to thread through.
    """

    ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.groq_api_key
        self._model = settings.groq_model
        self._client = httpx.AsyncClient(
            base_url="https://api.groq.com",
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        log.info("groq client ready", extra={"model": self._model})

    async def aclose(self) -> None:
        await self._client.aclose()

    async def stream(
        self,
        *,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        system_instruction: str,
        previous_interaction_id: str | None = None,
        tool_results: Sequence[ToolResult] = (),
    ) -> AsyncIterator[TurnResult]:
        payload: list[dict[str, Any]] = [
            {"role": "system", "content": system_instruction},
            *[
                {"role": "user" if m.role == "user" else "assistant", "content": m.text}
                for m in messages
            ],
        ]

        # Tool results are ordinary messages here, not a continuation of an
        # interaction, so `previous_interaction_id` is ignored on this path. That
        # asymmetry with Gemini is exactly why the loop goes through the
        # interface instead of calling either SDK directly.
        for result in tool_results:
            payload.append(
                {
                    "role": "tool",
                    "tool_call_id": result.call_id,
                    "content": json.dumps(result.result if result.ok else {"error": result.error}),
                }
            )

        payload_tools = [self._to_openai_tool(spec) for spec in tools] if tools else None

        body: dict[str, Any] = {
            "model": self._model,
            "messages": payload,
            "stream": False,
        }
        if payload_tools:
            body["tools"] = payload_tools
            body["tool_choice"] = "auto"

        response = await self._client.post(
            "/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=body,
        )
        response.raise_for_status()
        data = response.json()

        turn = TurnResult()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}

        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            # arguments arrive as a JSON string, not a dict.
            arguments = function.get("arguments") or "{}"
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError:
                log.warning("groq returned unparseable arguments for %s", function.get("name"))
                parsed = {}
            turn.tool_calls.append(
                ToolCall(id=raw.get("id") or "", name=function.get("name") or "", arguments=parsed)
            )

        turn.text = message.get("content") or ""
        usage = data.get("usage") or {}
        turn.prompt_tokens = usage.get("prompt_tokens", 0)
        turn.completion_tokens = usage.get("completion_tokens", 0)
        yield turn

    @staticmethod
    def _to_openai_tool(spec: ToolSpec) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }


# --- Factory ----------------------------------------------------------------


class FailoverClient:
    """One provider with the other one waiting behind it.

    Up to `max_attempts` calls on each provider, in order: the primary until it
    runs out of tries, then the fallback for the rest of the turn. Both providers
    failing re-raises the last error, which the router already turns into the
    ordinary SSE error frame — no new failure vocabulary for one adapter.

    ## Retries are only safe because of the yields

    A leg is retried from scratch, which is only correct while no turn has been
    yielded to the caller yet: a retried leg that already emitted text would
    duplicate it downstream. Both current adapters do all provider I/O before
    their single end-of-leg yield, so this holds today — an adapter that ever
    emits incremental yields must not be listed here.
    """

    def __init__(self, primary: LLMClient, fallback: LLMClient | None, max_attempts: int) -> None:
        # `(label, client)` rows; a class name is the label. A skipped fallback
        # collapses to a plain primary after construction.
        self._rows: list[tuple[str, LLMClient]] = [("primary", primary)]
        if fallback is not None:
            self._rows.append(("fallback", fallback))
        self._max_attempts = max_attempts

    async def stream(
        self,
        *,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        system_instruction: str,
        previous_interaction_id: str | None = None,
        tool_results: Sequence[ToolResult] = (),
    ) -> AsyncIterator[TurnResult]:
        last: Exception | None = None
        for label, client in self._rows:
            for attempt in range(1, self._max_attempts + 1):
                try:
                    async for turn in client.stream(
                        messages=messages,
                        tools=tools,
                        system_instruction=system_instruction,
                        previous_interaction_id=previous_interaction_id,
                        tool_results=tool_results,
                    ):
                        yield turn
                    return
                except (asyncio.CancelledError, GeneratorExit):
                    # The client went away. Recovery is not for us to attempt.
                    raise
                except Exception as exc:
                    # Broad on purpose: providers raise different exception
                    # types, and the fallback exists for the whole lot. An
                    # adapter bug would also flip over here, and that is the
                    # accepted trade — the visitor keeps an answer path and the
                    # log names every failure.
                    last = exc
                    log.warning(
                        "llm %s attempt %d/%d failed (%s): %s",
                        label,
                        attempt,
                        self._max_attempts,
                        type(client).__name__,
                        exc,
                    )
                    if attempt < self._max_attempts:
                        await asyncio.sleep(0.5 * attempt)
        assert last is not None  # at least one attempt always ran
        raise last


def _fallback(settings: Settings, provider: str) -> LLMClient | None:
    """The other provider, when its credentials exist.

    A missing fallback key is a logged shrug, not a boot failure: failing over
    is glue, not a requirement, and the strict key check for the *configured*
    provider is untouched — a silent primary would still evaluate the wrong
    model.
    """
    other = "groq" if provider == "gemini" else "gemini"
    if other == "groq":
        if not settings.groq_api_key:
            log.info("no groq fallback: GROQ_API_KEY empty")
            return None
        return GroqClient(settings)
    if not settings.gemini_api_key:
        log.info("no gemini fallback: GEMINI_API_KEY empty")
        return None
    return GeminiClient(settings)


def build_llm_client(settings: Settings) -> LLMClient:
    """Return the configured provider adapter, wrapped for failover.

    Raises rather than falling back silently when the configured provider is
    unknown, or when its key is missing where the config demands one: a fallback
    that hides a missing API key produces answers from a different model than
    the one you think you are evaluating, and phase 8's evals would quietly
    measure the wrong thing.
    """
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        primary: LLMClient = GeminiClient(settings)
    elif provider == "groq":
        primary = GroqClient(settings)
    else:
        raise ValueError(f"unknown LLM_PROVIDER {settings.llm_provider!r}; expected gemini or groq")

    return FailoverClient(primary, _fallback(settings, provider), settings.llm_max_attempts)


# --- Argument validation ----------------------------------------------------


class EchoArgs(BaseModel):
    """Schema for the phase-3 stub tool.

    Exists to prove the loop end to end before the real tools land in phase 5.
    Validating here rather than in the handler means a model that invents an
    argument gets a clear error instead of a `TypeError` from somewhere deeper.
    """

    text: str = Field(min_length=1, max_length=500)


def validate_arguments(tool: Any, arguments: dict[str, Any]) -> BaseModel | None:
    """Validate raw model arguments against a Pydantic model.

    Returns None on success, or a message describing what was wrong. Returning
    the complaint rather than raising is deliberate: the loop feeds it back to
    the model as a tool result, so the model can correct itself instead of the
    visitor seeing a failure.
    """
    try:
        tool.model_validate(arguments)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return f"invalid arguments: {problems}"
    return None
