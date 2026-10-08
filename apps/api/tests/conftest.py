"""Shared fixtures. Deliberately thin: no database, no API keys, no network.

Every test in this suite runs with an empty environment, which is the point. If
a test needs a credential to pass, it is testing your `.env`, not the code.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    """Undo any `get_settings()` override so tests do not leak into each other."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A client bound to the real app, with no outbound network available."""
    with TestClient(app) as test_client:
        yield test_client
