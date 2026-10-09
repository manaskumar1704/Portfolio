"""POST /chat, streaming over SSE.

The router's only job is turning `StreamEvent` objects into SSE frames. It holds
no prompt text, makes no tool decisions, and does not know which provider is
configured — all of that is in `services/chat.py`.

## Why SSE and not WebSockets

The traffic is one-directional once the request starts. SSE is plain HTTP, works
through Render's free tier and Vercel's edge without a special upgrade, and
reconnects on its own. WebSockets would add a protocol, a dependency, and a
connection-management problem to deliver the same bytes.

## The one non-obvious thing here

`StreamingResponse` sends the first byte as soon as the body is ready, which
keeps Render from holding the connection open waiting for a full answer. The
`X-Accel-Buffering: no` header stops nginx-style proxies from buffering the
stream into one lump at the end — without it, SSE works in development and
arrives all at once in production.
"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.logging import get_logger
from app.core.ratelimit import RateLimiter
from app.schemas.chat import ChatRequest
from app.services.chat import StreamEvent, run_chat_turn
from app.services.llm import ChatMessage, build_llm_client

router = APIRouter(tags=["chat"])
log = get_logger(__name__)

# Phase 6 tunes the limits and moves the counters somewhere durable. Built here
# now so the endpoint's shape does not change when that lands.
_limiter = RateLimiter()


def _frame(event: StreamEvent) -> str:
    """One SSE frame: an event name, then a JSON payload.

    Named events rather than bare `data:` lines so the frontend can switch on the
    type and ignore anything it does not recognise, instead of parsing a shape it
    was not expecting.
    """
    payload = json.dumps(event.data, default=str)
    return f"event: {event.kind}\ndata: {payload}\n\n"


@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    # Schema validation already bounded the message and the history length, so
    # an oversized request never reaches the provider. No second check needed.
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = _limiter.check(client_ip)
    if not allowed:
        log.info("rate limited %s", client_ip)
        busy = StreamEvent(
            "busy",
            {
                "retry_after_seconds": retry_after,
                "message": "Too many questions at once. Try again in a moment.",
            },
        )
        # Framed directly rather than through `_frames`, which is an async
        # generator over an async iterator. Passing a list here raised a
        # TypeError inside the generator and turned a clean 429 into a 500.
        return StreamingResponse(
            _frame(busy),
            media_type="text/event-stream",
            status_code=429,
            headers={"retry-after": str(retry_after)},
        )

    llm = build_llm_client(_settings())

    history = [ChatMessage(role=turn.role, text=turn.text) for turn in body.history]
    log.info(
        "chat turn",
        extra={"history_turns": len(history), "chars": len(body.message)},
    )

    return StreamingResponse(
        _frames(run_chat_turn(llm, body.message, history)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Without this a buffering proxy delivers the whole answer at once,
            # which looks like the stream is broken in production only.
            "X-Accel-Buffering": "no",
        },
    )


async def _frames(events: AsyncIterator[StreamEvent]) -> AsyncIterator[str]:
    """Turn events into frames, and guarantee exactly one `done`.

    `run_chat_turn` emits `done` on the happy path. If it raises partway through,
    the visitor never gets one and the frontend waits forever on a request that
    already failed. So `done` is tracked rather than appended unconditionally:
    appending it in `finally` as well would send two on every successful turn,
    and a client treating the second as a new turn would render the answer
    twice.
    """
    sent_done = False
    try:
        async for event in events:
            sent_done = sent_done or event.kind == "done"
            yield _frame(event)
    except Exception:
        log.exception("chat stream failed")
        yield _frame(StreamEvent("error", {"message": "Something went wrong. Try again."}))
    finally:
        if not sent_done:
            yield _frame(StreamEvent("done", {"sources": []}))


def _settings():
    """Read once per request; `get_settings` is cached, so this is cheap."""
    from app.core.config import get_settings

    return get_settings()
