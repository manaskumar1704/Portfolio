"""Request and response models for `POST /chat`.

`ChatReply` is the whole-payload shape `apps/web/src/lib/api/types.ts` already
expects from the backend, kept exactly so the fixture swap is a one-file
change. The event models are the SSE wire format added in phase 3; the
frontend's stream reader is the only other consumer.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ChatRole = Literal["user", "bot"]

# Bound the input. 4k characters is roughly a long paragraph and well past
# anything a recruiter types; it exists so one request cannot cost a thousand
# prompt tokens before the guardrails even see it.
MAX_MESSAGE_CHARS = 4_000
MAX_HISTORY = 10


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[str, Field(min_length=1, max_length=MAX_MESSAGE_CHARS)]
    # The client owns the conversation. We hold no history server-side: portfolio
    # visitors are anonymous and mostly single-turn, so there is nothing to read
    # back and nothing worth storing.
    history: Annotated[list["HistoryTurn"], Field(max_length=MAX_HISTORY)] = Field(
        default_factory=list
    )


class HistoryTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ChatRole
    text: Annotated[str, Field(max_length=MAX_MESSAGE_CHARS)]


class ChatReply(BaseModel):
    """The non-streaming shape. Matches the frontend's `ChatReply` type."""

    reply: str


# --- SSE wire format -------------------------------------------------------
#
# Each frame is `event: <name>` plus a JSON `data:` payload of the model below.
# Named events let the frontend ignore a type it does not know instead of
# choking on an unexpected shape, which is why this is not bare NDJSON.


class DeltaEvent(BaseModel):
    """A fragment of assistant prose. Concatenate `text` to render."""

    text: str


class ToolCallEvent(BaseModel):
    """The model asked for a tool. `id` matches the following ToolResultEvent."""

    id: str
    name: str
    arguments: dict


class ToolResultEvent(BaseModel):
    id: str
    name: str
    ok: bool
    result: object
    # Shown to the visitor. Never the raw traceback.
    error: str | None = None


class CitationEvent(BaseModel):
    """Provenance for a claim the model just made."""

    source_path: str
    label: str


class DraftEvent(BaseModel):
    """A message is waiting for the visitor's approval. Not sent yet.

    `approval_token` goes to the browser only. It must never enter a prompt, a
    log line, or a tool result, or the model can talk a visitor into sending.
    """

    id: int
    name: str
    email: str
    body: str
    approval_token: str


class BusyEvent(BaseModel):
    """Rate limited or the upstream provider is saturated. Not an error."""

    retry_after_seconds: int
    message: str


class ErrorEvent(BaseModel):
    message: str


class DoneEvent(BaseModel):
    """Terminal frame. `sources` is every citation seen in this answer."""

    sources: list[str] = Field(default_factory=list)


ChatRequest.model_rebuild()
