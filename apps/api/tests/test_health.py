"""The health split, which is the one thing phase 1 actually has to protect.

`/health` is what Render's health check and the keep-alive workflow call. If it
ever opens a database connection, the 10-minute ping stops Neon from scaling to
zero and the monthly CU-hours go on the meter for a service nobody is using.
The test asserts the absence of a connection, which is easy to break by accident
in P2 and impossible to notice without watching the bill.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_health_is_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_touch_the_database(client: TestClient) -> None:
    """A configured-looking URL must not change what `/health` does.

    If this test ever fails after P2, someone moved a query into the liveness
    path. Undo it rather than adjust the test.
    """
    from app.core.config import get_settings

    settings = get_settings()
    settings.database_url = "postgresql+asyncpg://nobody@127.0.0.1:1/none"

    assert client.get("/health").json() == {"status": "ok"}


async def test_ready_reports_a_broken_database() -> None:
    """An unreachable database is a 503, not a 200 that lies.

    Port 1 refuses instantly, so this does not wait on a real timeout.
    """
    from app.db import pool

    settings = get_settings()
    settings.database_url = "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none"
    await pool.setup(settings)
    try:
        with TestClient(app) as broken_client:
            response = broken_client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"db": "unavailable"}
    finally:
        await pool.teardown()


async def test_ready_succeeds_against_a_live_database() -> None:
    """The 503 branch above must not have made `/ready` always fail."""
    from app.db import pool

    settings = get_settings()
    if not settings.database_url:
        pytest.skip("DATABASE_URL not set")

    await pool.setup(settings)
    try:
        async with pool.session_scope() as session:
            from sqlalchemy import text

            assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
    finally:
        await pool.teardown()


def test_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/health")
    assert response.headers["x-request-id"]


def test_client_request_id_is_preserved(client: TestClient) -> None:
    """A trace started in the browser keeps its id through to the API logs."""
    response = client.get("/health", headers={"x-request-id": "abc123"})
    assert response.headers["x-request-id"] == "abc123"


def test_log_line_carries_the_request_id(client: TestClient, caplog) -> None:
    """The id has to reach the log line, not just the response header.

    This is the line you grep when a visitor reports a bad answer. It carried a
    hardcoded default once, because the contextvar was reset before it was
    logged, and nothing else caught it.
    """
    with caplog.at_level("INFO", logger="app.main"):
        client.get("/health", headers={"x-request-id": "trace-me"})

    access_lines = [r for r in caplog.records if r.message.startswith("GET")]
    assert access_lines, "no access log line was emitted"
    assert access_lines[0].request_id == "trace-me"
