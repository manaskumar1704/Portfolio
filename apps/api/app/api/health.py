"""Liveness and readiness.

Two endpoints, and the split is load-bearing: Render's health check and the
keep-alive ping hit `/health`, which must never touch Postgres. If it did, the
ping would hold Neon out of scale-to-zero and burn the monthly CU-hours for
nothing. `/ready` is the one that opens a connection, for diagnosing a
database problem without shipping that cost into the health check.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness. Deliberately touches nothing: no DB, no LLM, no network."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    """Readiness. Says `not configured` until P2 gives it a pool to query."""
    return {"db": "not configured"}
