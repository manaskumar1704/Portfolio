"""The lifespan refuses to serve an unusable production configuration.

Separate from `test_production_config.py`, which tests the rules. This tests the
consequence: does the container actually stop?

That is the claim worth pinning. A check that computes the right problems and a
caller that ignores them produces a deployment that boots broken, and the tests
would still be green.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

BASE = {
    "app_env": "production",
    "database_url": "postgresql://u:p@host/db",
    "sync_database_url": "postgresql://u:p@host/db",
    "gemini_api_key": "a-real-looking-key",
    "cors_origins": ["https://example.com"],
    "ip_hash_salt": "a-sufficiently-long-salt",
    "resend_api_key": "re_key",
    "contact_notify_email": "owner@example.com",
    "trusted_proxy_cidrs": ["10.0.0.5"],
}


def configure(monkeypatch, **overrides):
    """Point the app's module-level `settings` at a given configuration.

    `app.main` reads `get_settings()` once at import, so patching the config class
    after the fact would not reach the lifespan. The attribute the lifespan
    actually closes over is the one to replace.
    """
    settings = get_settings()
    for key, value in {**BASE, **overrides}.items():
        setattr(settings, key, value)
    monkeypatch.setattr("app.main.settings", settings)
    return settings


def test_a_complete_production_configuration_starts(monkeypatch) -> None:
    configure(monkeypatch)

    with TestClient(app):
        pass


def test_a_missing_database_url_stops_the_container(monkeypatch) -> None:
    """The one that matters most: a booted app with no database answers `/health`
    forever and 500s on every real request."""
    configure(monkeypatch, database_url="")

    with pytest.raises(RuntimeError) as exc, TestClient(app):
        pass

    assert "DATABASE_URL" in str(exc.value)


def test_the_failure_names_every_problem_at_once(monkeypatch) -> None:
    """One boot cycle, one log line. Fixing them one deploy at a time wastes a
    deploy per variable, and each failed deploy costs the previous working one."""
    configure(monkeypatch, database_url="", cors_origins=[], ip_hash_salt="short")

    with pytest.raises(RuntimeError) as exc, TestClient(app):
        pass

    message = str(exc.value)
    assert "DATABASE_URL" in message
    assert "CORS_ORIGINS" in message
    assert "IP_HASH_SALT" in message


def test_an_empty_trust_list_does_not_stop_the_container(monkeypatch) -> None:
    """Expected on a first deploy, and its only fix is a probe run against a
    deployed instance — so failing here would deadlock the setup."""
    configure(monkeypatch, trusted_proxy_cidrs=[])

    with TestClient(app):
        pass


def test_a_local_environment_is_never_held_to_the_production_contract(monkeypatch) -> None:
    """The `test` job runs with no database and no keys, on purpose."""
    configure(monkeypatch, app_env="local", database_url="", cors_origins=[], ip_hash_salt="")

    with TestClient(app):
        pass


def test_the_check_runs_before_any_connection_is_attempted(monkeypatch) -> None:
    """Ordering is load-bearing.

    A configuration check that opens a connection cannot report "your database URL
    is wrong" — the failure would be a connection error, with the real cause
    somewhere underneath it. So the check is pure and runs first, and the strongest
    evidence is that a bad `DATABASE_URL` produces *our* message rather than
    asyncpg's.
    """
    import app.main as main_module

    attempts = []

    async def never_called(settings):
        attempts.append(settings.database_url)

    monkeypatch.setattr(main_module.db, "setup", never_called)
    configure(monkeypatch, database_url="")

    with pytest.raises(RuntimeError) as exc, TestClient(app):
        pass

    assert "DATABASE_URL is empty" in str(exc.value)
    assert attempts == [], "a connection was attempted before the configuration check"