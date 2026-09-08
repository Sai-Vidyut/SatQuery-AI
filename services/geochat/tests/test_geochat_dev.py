"""Tests for GeoChat developer manager helpers."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from geochat_dev.acceptance import run_real_provider_acceptance
from geochat_dev.client import GeoChatDevClient
from geochat_dev.composite import build_evidence_composite_smoke
from geochat_dev.config import GeoChatDevConfig, load_config


@pytest.fixture
def real_config() -> GeoChatDevConfig:
    return GeoChatDevConfig(
        provider="geochat_service",
        service_url="https://example.ngrok.app",
        model_id="MBZUAI/geochat-7B",
        timeout_s=30.0,
        env_file=None,
        env_file_loaded=False,
    )


def test_load_config_defaults_development(monkeypatch, tmp_path):
    monkeypatch.delenv("GEOCHAT_VQA_PROVIDER", raising=False)
    monkeypatch.delenv("GEOCHAT_SERVICE_URL", raising=False)
    missing = tmp_path / "missing.env"
    config = load_config(env_file=missing)
    assert config.provider == "development"
    assert config.service_url is None


def test_build_evidence_composite_smoke_is_png():
    png = build_evidence_composite_smoke()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000


def test_status_local_mode():
    config = GeoChatDevConfig(
        provider="development",
        service_url=None,
        model_id="MBZUAI/geochat-7B",
        timeout_s=30.0,
        env_file=None,
        env_file_loaded=False,
    )
    status = GeoChatDevClient(config).status()
    assert status.real_mode_configured is False
    assert "development" in status.message


def test_status_real_mode_without_url():
    config = GeoChatDevConfig(
        provider="geochat_service",
        service_url=None,
        model_id="MBZUAI/geochat-7B",
        timeout_s=30.0,
        env_file=None,
        env_file_loaded=False,
    )
    status = GeoChatDevClient(config).status()
    assert status.real_mode_configured is False
    assert "GEOCHAT_SERVICE_URL is not set" in status.message


def test_status_unreachable_service(real_config, monkeypatch):
    def _fail(*args, **kwargs):
        raise httpx.ConnectError("connection refused", request=httpx.Request("GET", "https://example.ngrok.app/health"))

    monkeypatch.setattr(httpx, "get", _fail)
    status = GeoChatDevClient(real_config).status()
    assert status.reachable is False
    assert status.tunnel_public is True


def test_status_ready_service(real_config, monkeypatch):
    def _health(url, timeout):
        assert url.endswith("/health")
        response = httpx.Response(
            200,
            json={
                "status": "ok",
                "model_loaded": True,
                "model_name": "MBZUAI/geochat-7B",
                "provider": "geochat_service",
                "gpu": "Tesla T4",
                "startup_state": "ready",
            },
            request=httpx.Request("GET", url),
        )
        return response

    monkeypatch.setattr(httpx, "get", _health)
    status = GeoChatDevClient(real_config).status()
    assert status.model_loaded is True
    assert status.reachable is True


def test_smoke_test_blocked_when_unreachable(real_config, monkeypatch):
    def _fail(*args, **kwargs):
        raise httpx.ConnectError("down", request=httpx.Request("GET", "https://example.ngrok.app/health"))

    monkeypatch.setattr(httpx, "get", _fail)
    result = GeoChatDevClient(real_config).smoke_test(composite=True)
    assert result.status == "BLOCKED"
    assert result.blocked is True


def test_smoke_test_rejects_development_mock(real_config, monkeypatch):
    def _health(url, timeout):
        return httpx.Response(
            200,
            json={"status": "ok", "model_loaded": True, "model_name": "MBZUAI/geochat-7B", "provider": "geochat_service", "gpu": "T4", "startup_state": "ready"},
            request=httpx.Request("GET", url),
        )

    def _post(url, json, timeout):
        return httpx.Response(
            200,
            json={
                "answer": "[development mock — not MBZUAI/geochat-7B] fake",
                "model_name": "MBZUAI/geochat-7B",
                "provider": "geochat_service",
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "get", _health)
    monkeypatch.setattr(httpx, "post", _post)
    result = GeoChatDevClient(real_config).smoke_test(composite=True)
    assert result.status == "FAIL"
    assert "development mock" in (result.error or "").lower()


def test_acceptance_blocked_in_development_mode():
    config = GeoChatDevConfig(
        provider="development",
        service_url=None,
        model_id="MBZUAI/geochat-7B",
        timeout_s=30.0,
        env_file=None,
        env_file_loaded=False,
    )
    result = run_real_provider_acceptance(config, include_satquery_adapter=False)
    assert result.status == "BLOCKED"


def test_acceptance_passes_with_mocked_service(real_config, monkeypatch):
    def _health(url, timeout):
        return httpx.Response(
            200,
            json={"status": "ok", "model_loaded": True, "model_name": "MBZUAI/geochat-7B", "provider": "geochat_service", "gpu": "T4", "startup_state": "ready"},
            request=httpx.Request("GET", url),
        )

    def _post(url, json, timeout):
        return httpx.Response(
            200,
            json={
                "answer": "Vegetation appears reduced in the after panel compared with before.",
                "model_name": "MBZUAI/geochat-7B",
                "provider": "geochat_service",
                "model_version": "7B",
                "provenance": {"model_name": "MBZUAI/geochat-7B", "provider": "geochat_service", "service_version": "0.1.0"},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "get", _health)
    monkeypatch.setattr(httpx, "post", _post)
    result = run_real_provider_acceptance(real_config, include_satquery_adapter=False)
    assert result.status == "PASS"
    names = [check.name for check in result.checks]
    assert "service_health" in names
    assert "composite_vqa" in names


def test_geochat_dev_cli_status_development():
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parents[3]
    env = dict(**__import__("os").environ)
    env["GEOCHAT_VQA_PROVIDER"] = "development"
    env.pop("GEOCHAT_SERVICE_URL", None)
    proc = subprocess.run(
        [sys.executable, str(repo_root / "services" / "geochat" / "scripts" / "geochat_dev.py"), "status"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.split("\n\n")[0])
    assert payload["provider"] == "development"
