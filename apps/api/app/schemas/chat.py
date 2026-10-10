"""Request and response models for `POST /chat`.

`ChatRequest` is the only model the route actually validates. The response is
`text/event-stream`, not a payload, so there is no reply model here.

## Why there are no event models

Phase 3 wrote seven `*Event` Pydantic models to document the SSE wire format.
They were never used — `services/chat.py` builds a `StreamEvent` dataclass with
a plain dict payload and the router serialises it — and they drifted:

- `DraftEvent` had no `expires_at`, which the emitter has sent since phase 6.
- `DoneEvent` had no `text_length`, which the emitter has sent since phase 3.

A model that is never validated and is missing fields reads as the contract while
being wrong, which is worse than having no model at all. They are deleted, and
`tests/test_contracts.py` now pins the event *names* directly against the
frontend's `ChatEvent` union, which is the real contract.

That check is live in a way the models never were: adding a new event to the
emitter without adding it to `types.ts` fails a test.
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


ChatRequest.model_rebuild()