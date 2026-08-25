"""Shared pytest fixtures for backend tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def force_development_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure API tests use development adapters unless a test overrides explicitly."""
    monkeypatch.setenv("IMAGERY_PROVIDER", "development")
    monkeypatch.setenv("CHANGE_DETECTOR", "development")
    monkeypatch.setenv("SEMANTIC_ANALYZER", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
