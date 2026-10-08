"""Config parsing and the bounds that protect the free tier.

These are the checks worth having now: every later phase reads `get_settings()`
and assumes these fields mean what the name says. A CSV that arrives as one
string instead of a list, or a rate limit of zero, fails quietly at 3am.
"""

from app.core.config import Settings, get_settings


def test_csv_env_vars_become_lists(monkeypatch) -> None:
    """CORS_ORIGINS=a,b arrives as a string; nothing downstream wants a string."""
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://x.dev ,")
    monkeypatch.setenv("GITHUB_PINS", "a/b, c/d")

    settings = Settings()

    assert settings.cors_origins == ["http://localhost:3000", "https://x.dev"]
    assert settings.github_pins == ["a/b", "c/d"]


def test_empty_csv_becomes_empty_list(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_PINS", "")
    assert Settings().github_pins == []


def test_tracing_is_off_until_both_keys_are_present(monkeypatch) -> None:
    """Half-configured tracing must stay off, not blow up on the first request."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    assert Settings().tracing_enabled is False

    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    assert Settings().tracing_enabled is True


def test_settings_are_cached() -> None:
    """Two calls, one object. Otherwise env changes mid-request surprise you."""
    assert get_settings() is get_settings()
