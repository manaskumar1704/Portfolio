"""The probe route's gate.

Temporary tests for a temporary route. They go when `app/api/probe.py` does.

The route reports the socket peer address, which is exactly what tells an
attacker whether a forged `X-Forwarded-For` is being believed. So the thing worth
testing is that it is closed by default and stays closed under the obvious
probes — an empty token, a wrong token, and a prefix of the right one.
"""

import httpx
import pytest
from fastapi import FastAPI

from app.api import probe
from app.core.config import Settings

TOKEN = "an-unguessable-probe-token"


def app_with(token: str) -> FastAPI:
    application = FastAPI()
    application.include_router(probe.router)
    return application


def settings_with(token: str, monkeypatch) -> None:
    """Patch the seam the route actually reads.

    `probe.py` imports `get_settings` by name, so the module attribute is bound
    at import and patching `app.core.config.get_settings` would never be seen.
    """
    monkeypatch.setattr(
        "app.api.probe.get_settings",
        lambda: Settings(probe_token=token),
    )


async def request(application: FastAPI, token: str = "") -> httpx.Response:
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(f"/_probe/headers?token={token}")


@pytest.mark.asyncio
async def test_an_unset_token_means_the_route_does_not_exist(monkeypatch) -> None:
    """The default deployment. No token configured, nothing to find."""
    settings_with("", monkeypatch)

    assert (await request(app_with(TOKEN))).status_code == 404


@pytest.mark.asyncio
async def test_the_right_token_reports_what_the_deployment_sees(monkeypatch) -> None:
    settings_with(TOKEN, monkeypatch)

    response = await request(app_with(TOKEN), TOKEN)

    assert response.status_code == 200
    assert "peer" in response.json()


@pytest.mark.asyncio
async def test_a_wrong_token_is_refused(monkeypatch) -> None:
    settings_with(TOKEN, monkeypatch)

    assert (await request(app_with(TOKEN), "not-the-token")).status_code == 404


@pytest.mark.asyncio
async def test_an_empty_token_is_refused_even_when_one_is_configured(monkeypatch) -> None:
    """The `token=` present but blank case, which is the easy one to get wrong."""
    settings_with(TOKEN, monkeypatch)

    assert (await request(app_with(TOKEN), "")).status_code == 404


@pytest.mark.asyncio
async def test_a_prefix_of_the_token_is_refused(monkeypatch) -> None:
    """Why this is a `compare_digest` and not `==`.

    A prefix is the natural thing to guess, and an implementation using `==` on
    a comparison that short-circuits would need this test to fail. It pins the
    property rather than the mechanism.
    """
    settings_with(TOKEN, monkeypatch)

    assert (await request(app_with(TOKEN), TOKEN[:-1])).status_code == 404


@pytest.mark.asyncio
async def test_a_refusal_is_404_not_403(monkeypatch) -> None:
    """A 403 confirms the route is here, which is the start of a second attempt.

    404 is indistinguishable from a deployment where the route was already
    removed.
    """
    settings_with(TOKEN, monkeypatch)

    assert (await request(app_with(TOKEN), "wrong")).status_code == 404


@pytest.mark.asyncio
async def test_the_response_shows_what_the_trust_list_resolves_to(monkeypatch) -> None:
    """The field that makes the exercise iterative.

    `peer` says what to add. `currently_resolves_to` says whether what is already
    there works — the difference between a populated list and a plausible one.
    """
    settings_with(TOKEN, monkeypatch)

    body = (await request(app_with(TOKEN), TOKEN)).json()

    assert "currently_resolves_to" in body
    assert "trusted_proxy_count" in body
