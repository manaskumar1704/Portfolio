"""App entrypoint.

Start with `uv run uvicorn app.main:app --reload` from `apps/api`.

Deliberately thin. Routers are included, middleware is registered, and nothing
else happens here: any logic that grows past a few lines of wiring belongs in
a service, so the chat endpoint and the MCP server can both call it.
"""

import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, health, messages, probe
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, request_id
from app.core.retention import sweep_on_boot
from app.db import pool as db

log = get_logger(__name__)
settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(
        "startup",
        extra={"env": settings.app_env, "llm": settings.llm_provider},
    )
    if settings.database_url:
        await db.setup(settings)
        # Retention on boot. There is no cron on this tier, so container start is
        # the one reliable trigger. Swallows its own failures: a DELETE that
        # errors must not stop the app from serving /health.
        await sweep_on_boot(settings)
    else:
        # Local development and CI both run without a database. The app starts
        # so `/health` still answers; anything that needs Postgres fails loudly
        # on its own endpoint rather than taking the whole service down.
        log.warning("DATABASE_URL is not set; database-backed endpoints are unavailable")

    # A missing GitHub configuration is a warning, not a boot failure: the tool
    # reports "unavailable" to the model and the rest of the site works.
    try:
        settings.require_github()
    except RuntimeError as exc:
        log.warning("github tool disabled: %s", str(exc).split(".")[0])

    try:
        yield
    finally:
        # P3 closes the LLM HTTP client here. Closing connections on the way out
        # is what keeps a redeploy from leaking sockets into Render's ephemeral
        # filesystem until the container is replaced.
        await db.teardown()


app = FastAPI(
    title="AI Portfolio API",
    version="0.1.0",
    lifespan=lifespan,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Tag each request with an id and time it.

    The id comes from the client when it sends one, so a trace started in the
    browser keeps its id through to the API logs.
    """
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = request_id.set(rid)
    started = time.perf_counter()

    try:
        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info(
            "%s %s -> %d in %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        response.headers["x-request-id"] = rid
        return response
    except Exception:
        # Log before re-raising: FastAPI turns the exception into a 500, and
        # without this line the failure leaves no trace at all.
        log.exception("unhandled %s %s", request.method, request.url.path)
        raise
    finally:
        # After both logs, not before. Resetting earlier left the request id
        # back at its "-" default on the success line, which is the one line
        # you go looking for when a visitor reports a bad answer.
        request_id.reset(token)


app.include_router(health.router)
app.include_router(chat.router)
app.include_router(messages.router)
app.include_router(probe.router)
