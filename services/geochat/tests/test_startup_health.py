"""Startup /health state tests (no GPU)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from geochat_service.config import ServiceConfig
from geochat_service.inference import GeoChatInferenceEngine, ModelUnavailableError


def test_engine_starts_idle() -> None:
    engine = GeoChatInferenceEngine(
        ServiceConfig(
            model_id="MBZUAI/geochat-7B",
            geochat_src=None,
            host="127.0.0.1",
            port=8080,
            eager_load=False,
            hf_token=None,
            service_version="0.1.0",
        )
    )
    assert engine.startup_state == "idle"
    assert engine.model_loaded is False


def test_engine_load_fails_without_geochat_src() -> None:
    engine = GeoChatInferenceEngine(
        ServiceConfig(
            model_id="MBZUAI/geochat-7B",
            geochat_src=None,
            host="127.0.0.1",
            port=8080,
            eager_load=False,
            hf_token=None,
            service_version="0.1.0",
        )
    )
    with pytest.raises(ModelUnavailableError):
        engine.load()
    assert engine.startup_state == "failed"
    assert engine.load_error
    assert engine.model_loaded is False


def test_fake_engine_health_reports_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEOCHAT_SERVICE_FAKE_ENGINE", "true")
    # Re-import app with fake engine
    import importlib

    import geochat_service.main as main_module

    importlib.reload(main_module)
    client = TestClient(main_module.app)
    res = client.get("/health")
    body = res.json()
    assert body["startup_state"] == "ready"
    assert body["model_loaded"] is True
    assert body["status"] == "ok"
