"""Liveness and readiness.

Two endpoints, and the split is load-bearing: Render's health check and the
keep-alive ping hit `/health`, which must never touch Postgres. If it did, the
ping would hold Neon out of scale-to-zero and burn the monthly CU-hours for
nothing. `/ready` is the one that opens a connection, for diagnosing a
database problem without shipping that cost into the health check.
"""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.logging import get_logger
from app.db import pool

router = APIRouter(tags=["health"])
log = get_logger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness. Deliberately touches nothing: no DB, no LLM, no network."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, str]:
    """Readiness. Opens a connection on purpose, unlike `/health`.

    A suspended Neon compute wakes in a few hundred milliseconds on first
    query, so the first call after a quiet spell is slower than the rest. That
    is expected, not a fault.
    """
    try:
        async with pool.session_scope() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        log.warning("readiness check failed: %s", exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"db": "unavailable"}

    return {"db": "ok"}
