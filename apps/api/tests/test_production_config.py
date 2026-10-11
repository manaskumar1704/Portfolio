"""What production refuses to start without, and what it merely mentions.

The distinction is the whole point. A configuration problem whose absence is
*silent* must stop the container, because the alternative is an app that boots,
answers `/health`, and fails in front of a visitor. One whose absence is *expected
on a first deploy* must not, because the fix requires a person to run a probe and
read the answer — and failing would block the deploy needed to discover it.
"""

import pytest

from app.core.config import Settings

# Every variable Settings reads. Cleared for the whole module.
#
# This test file asserts things about CONFIGURATION, so it must not be able to see
# the developer's own .env. It previously could, and the consequence was a test
# that passed on one machine and failed in CI.
#
# Two separate mechanisms, because they do different jobs:
#
#   monkeypatch.delenv  removes the process environment. `uv run pytest` inherits
#                       whatever the shell exported, and a DATABASE_URL exported
#                       in a shell profile reaches the test the same way a .env
#                       reaches it.
#   _env_file=None      stops pydantic-settings reading the .env file on disk.
#
# Setting only _env_file=None leaves the process environment intact, which is why
# the first attempt at this fix was not enough.
ENV_VARS = (
    "DATABASE_URL",
    "SYNC_DATABASE_URL",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "CORS_ORIGINS",
    "IP_HASH_SALT",
    "RESEND_API_KEY",
    "CONTACT_NOTIFY_EMAIL",
    "RESEND_FROM",
    "TRUSTED_PROXY_CIDRS",
    "GITHUB_TOKEN",
    "GITHUB_OWNER",
    "GITHUB_PINS",
    "APP_ENV",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
)


@pytest.fixture(autouse=True)
def _isolate_from_ambient_config(monkeypatch):
    """No test in this file may depend on the machine it runs on."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("app.core.config.Settings.__init__", _with_no_env_file(monkeypatch))
    yield


def _with_no_env_file(monkeypatch):
    """Return a Settings subclass that never reads a .env file."""
    original = Settings.__init__

    def patched(self, **kwargs):
        kwargs.setdefault("_env_file", None)
        return original(self, **kwargs)

    return patched


def production(**overrides) -> Settings:
    """A configuration that passes everything, so each test can break one thing."""
    base = {
        "app_env": "production",
        "database_url": "postgresql://u:p@host/db",
        "sync_database_url": "postgresql://u:p@host/db",
        "gemini_api_key": "a-real-looking-key",
        "cors_origins": ["https://example.com"],
        "ip_hash_salt": "a-sufficiently-long-salt",
        "resend_api_key": "re_key",
        "contact_notify_email": "owner@example.com",
        "trusted_proxy_cidrs": ["10.0.0.5"],
        "resend_from": "hello@example.com",
    }
    base.update(overrides)
    return Settings(**base)


# --- The switch -------------------------------------------------------------


def test_a_fully_configured_production_passes() -> None:
    assert production().production_problems() == []


def test_production_mode_is_off_by_default() -> None:
    """A checkout with no .env must not trip the production rules on a laptop."""
    assert Settings().is_production is False


def test_the_mode_switch_is_case_and_space_insensitive() -> None:
    assert Settings(app_env=" Production ").is_production is True


def test_a_local_configuration_is_never_problematic() -> None:
    """No database, no keys, no CORS — all normal locally.

    The first version of this test passed in CI for the wrong reason, and failed
    for the right one. It is kept because it pins the fix: `production_problems`
    must be empty when `APP_ENV` is not `production`, whatever the environment.
    """
    settings = Settings(app_env="local")

    assert settings.production_problems() == []


def test_production_problems_ignores_app_env_case_and_padding() -> None:
    """ "Production", "PRODUCTION" and " production " all mean production.

    A stray space in a Render environment variable would otherwise silently
    disable every boot check, which is the exact failure the checks exist to
    prevent.
    """
    for value in ("production", "PRODUCTION", " Production "):
        settings = Settings(app_env=value, database_url="")
        assert settings.production_problems(), value


def test_production_still_reports_every_problem() -> None:
    """The positive case the fix must not have broken.

    Gating on `is_production` could have been done by making the method always
    return an empty list, or by returning early before any check runs. Both would
    satisfy the test above. This one cannot be satisfied by either.
    """
    settings = production()

    assert settings.is_production is True
    assert settings.production_problems() == []


def test_production_reports_each_missing_variable_when_app_env_is_production() -> None:
    """One absent variable, named, with an explicit `app_env`.

    `production()` supplies everything else, so breaking one field yields exactly
    one problem. Asserted with no .env in scope and no ambient environment, so
    the result cannot come from the machine it runs on.
    """
    settings = production(database_url="", app_env="production")

    problems = settings.production_problems()

    assert len(problems) == 1, problems
    assert "DATABASE_URL" in problems[0]


def test_a_completely_empty_production_config_reports_five_problems() -> None:
    """The count, so a silently-dropped check fails here rather than nowhere."""
    settings = Settings(app_env="production")

    assert len(settings.production_problems()) == 5


# --- Fails: the silent absences ---------------------------------------------


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("database_url", "DATABASE_URL"),
        ("sync_database_url", "SYNC_DATABASE_URL"),
        ("gemini_api_key", "GEMINI_API_KEY"),
        ("cors_origins", "CORS_ORIGINS"),
        ("ip_hash_salt", "IP_HASH_SALT"),
    ],
)
def test_each_silent_absence_is_reported(field: str, expected: str) -> None:
    problems = production(**{field: ""}).production_problems()

    assert any(expected in problem for problem in problems), problems


def test_a_missing_database_url_names_the_variable_and_the_consequence() -> None:
    """Not just "unset" — a log line has to be enough to act on."""
    problems = " ".join(production(database_url="").production_problems())

    assert "DATABASE_URL" in problems
    assert "500" in problems


def test_a_missing_gemini_key_names_the_configured_provider() -> None:
    problems = " ".join(production(gemini_api_key="").production_problems())

    assert "GEMINI_API_KEY" in problems
    assert "LLM_PROVIDER" in problems


def test_the_gemini_key_is_not_demanded_when_groq_is_the_provider() -> None:
    settings = production(gemini_api_key="", llm_provider="groq", groq_api_key="gsk_real")

    assert settings.production_problems() == []


def test_a_missing_groq_key_is_reported_when_groq_is_the_provider() -> None:
    problems = production(
        gemini_api_key="", llm_provider="groq", groq_api_key=""
    ).production_problems()

    assert any("GROQ_API_KEY" in problem for problem in problems), problems


def test_a_short_salt_fails_because_it_makes_the_hash_reversible() -> None:
    problems = production(ip_hash_salt="short").production_problems()

    assert any("IP_HASH_SALT" in problem for problem in problems)
    assert any("brute force" in problem for problem in problems)


def test_sixteen_characters_is_the_floor() -> None:
    """The boundary, because `ip_hashing_enabled` uses the same number."""
    assert production(ip_hash_salt="a" * 16).production_problems() == []
    assert production(ip_hash_salt="a" * 15).production_problems() != []


# --- Fails: a half-configured pair is a typo --------------------------------


def test_a_resend_key_without_an_address_fails() -> None:
    problems = production(contact_notify_email="").production_problems()

    assert any("CONTACT_NOTIFY_EMAIL" in problem for problem in problems), problems


def test_an_address_without_a_resend_key_fails() -> None:
    problems = production(resend_api_key="").production_problems()

    assert any("RESEND_API_KEY" in problem for problem in problems), problems


def test_neither_resend_setting_is_not_an_error() -> None:
    """Email is optional. An unconfigured site should still serve questions."""
    assert production(resend_api_key="", contact_notify_email="").production_problems() == []


# --- Warns: expected on a first deploy --------------------------------------


def test_an_empty_trust_list_is_a_warning_not_a_problem() -> None:
    """Failing here would block the deploy needed to discover the value.

    The only fix is running GET /_probe/headers and reading `peer` back, so the
    deploy cannot be a precondition of having the answer.
    """
    settings = production(trusted_proxy_cidrs=[])

    assert settings.production_problems() == []
    assert any("TRUSTED_PROXY_CIDRS" in warning for warning in settings.production_warnings())


def test_the_trust_list_warning_says_what_is_broken_and_what_to_do() -> None:
    warning = " ".join(production(trusted_proxy_cidrs=[]).production_warnings())

    assert "X-Forwarded-For" in warning
    assert "_probe/headers" in warning


def test_the_default_sender_is_a_warning() -> None:
    """It works, but only delivers to the owner. Worth saying out loud."""
    settings = production(resend_from="onboarding@resend.dev")

    assert settings.production_problems() == []
    assert any("onboarding@resend.dev" in warning for warning in settings.production_warnings())


def test_a_verified_sender_is_not_warned_about() -> None:
    assert production(resend_from="hello@example.com").production_warnings() == []


def test_a_healthy_production_deployment_is_quiet() -> None:
    """The check that would fail if someone added a warning for everything."""
    assert production().production_warnings() == []


# --- What it does not check -------------------------------------------------


def test_github_is_not_a_production_problem() -> None:
    """Deliberate. An unconfigured GitHub tool reports "unavailable" to the model
    and the rest of the site works, which is better than not booting."""
    assert production(github_token="", github_owner="").production_problems() == []


def test_groq_is_not_demanded_when_gemini_works() -> None:
    assert production(groq_api_key="").production_problems() == []
