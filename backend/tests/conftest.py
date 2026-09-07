"""Shared pytest fixtures for backend tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def force_development_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure API tests use development adapters unless a test overrides explicitly."""
    monkeypatch.setenv("IMAGERY_PROVIDER", "development")
    monkeypatch.setenv("CHANGE_DETECTOR", "development")
    monkeypatch.setenv("SEMANTIC_ANALYZER", "development")
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "development")
    monkeypatch.setenv("UPLOAD_ALLOW_PNG_JPEG_WITHOUT_BENCHMARK", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.adapters.rsvlm.factory import get_geochat_vlm

    get_geochat_vlm.cache_clear()
    yield
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()
