"""HTTP helpers for GeoChat developer tooling."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from geochat_dev.composite import build_evidence_composite_smoke
from geochat_dev.config import GeoChatDevConfig


MOCK_MARKERS = ("development mock", "[development mock")


@dataclass
class GeoChatDevStatus:
    provider: str
    service_url: str | None
    redacted_service_url: str
    model_id: str
    real_mode_configured: bool
    reachable: bool
    health: dict[str, Any] | None = None
    health_error: str | None = None
    model_loaded: bool = False
    startup_state: str | None = None
    tunnel_public: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "service_url": self.redacted_service_url,
            "model_id": self.model_id,
            "real_mode_configured": self.real_mode_configured,
            "reachable": self.reachable,
            "model_loaded": self.model_loaded,
            "startup_state": self.startup_state,
            "tunnel_public": self.tunnel_public,
            "health": self.health,
            "health_error": self.health_error,
            "message": self.message,
        }


@dataclass
class SmokeTestResult:
    ok: bool
    blocked: bool
    status: str
    answer: str | None = None
    model_name: str | None = None
    provider: str | None = None
    composite: bool = False
    error: str | None = None
    response: dict[str, Any] | None = None


class GeoChatDevClient:
    def __init__(self, config: GeoChatDevConfig) -> None:
        self.config = config

    @property
    def service_url(self) -> str | None:
        return self.config.service_url

    def _require_service_url(self) -> str:
        if not self.config.service_url:
            raise ValueError("GEOCHAT_SERVICE_URL is not configured.")
        return self.config.service_url

    def fetch_health(self, *, timeout_s: float | None = None) -> dict[str, Any]:
        url = self._require_service_url()
        timeout = timeout_s if timeout_s is not None else min(self.config.timeout_s, 60.0)
        response = httpx.get(f"{url}/health", timeout=timeout)
        response.raise_for_status()
        return response.json()

    def status(self) -> GeoChatDevStatus:
        redacted = self.config.redacted_service_url()
        if not self.config.is_real_mode:
            return GeoChatDevStatus(
                provider=self.config.provider,
                service_url=self.config.service_url,
                redacted_service_url=redacted,
                model_id=self.config.model_id,
                real_mode_configured=False,
                reachable=False,
                message=(
                    "LOCAL development mode (GEOCHAT_VQA_PROVIDER=development). "
                    "Real GPU service checks are skipped."
                ),
            )

        if not self.config.service_url:
            return GeoChatDevStatus(
                provider=self.config.provider,
                service_url=None,
                redacted_service_url=redacted,
                model_id=self.config.model_id,
                real_mode_configured=False,
                reachable=False,
                message=(
                    "REAL mode selected but GEOCHAT_SERVICE_URL is not set. "
                    f"Copy {self.config.env_file or 'backend/.env.geochat-real.example'} "
                    "and paste your tunnel URL."
                ),
            )

        parsed = urlparse(self.config.service_url)
        tunnel_public = parsed.scheme == "https" and parsed.hostname not in {
            "127.0.0.1",
            "localhost",
        }

        try:
            health = self.fetch_health()
        except Exception as exc:
            return GeoChatDevStatus(
                provider=self.config.provider,
                service_url=self.config.service_url,
                redacted_service_url=redacted,
                model_id=self.config.model_id,
                real_mode_configured=True,
                reachable=False,
                health_error=str(exc),
                tunnel_public=tunnel_public,
                message=(
                    f"REAL mode configured ({redacted}) but service is unreachable. "
                    "Keep Colab/Kaggle session and ngrok tunnel alive."
                ),
            )

        model_loaded = bool(health.get("model_loaded"))
        startup_state = health.get("startup_state")
        reachable = health.get("status") in {"ok", "degraded"}
        if model_loaded and health.get("status") == "ok":
            msg = f"REAL GeoChat service ready at {redacted}."
        elif startup_state == "starting":
            msg = f"Service reachable at {redacted} but model is still loading."
        else:
            msg = f"Service reachable at {redacted} but not ready for inference."

        return GeoChatDevStatus(
            provider=self.config.provider,
            service_url=self.config.service_url,
            redacted_service_url=redacted,
            model_id=self.config.model_id,
            real_mode_configured=True,
            reachable=reachable,
            health=health,
            model_loaded=model_loaded,
            startup_state=startup_state,
            tunnel_public=tunnel_public,
            message=msg,
        )

    def wait_ready(
        self,
        *,
        timeout_s: float = 600.0,
        poll_s: float = 5.0,
    ) -> GeoChatDevStatus:
        deadline = time.time() + timeout_s
        last: GeoChatDevStatus | None = None
        while time.time() < deadline:
            last = self.status()
            if last.model_loaded and last.health and last.health.get("status") == "ok":
                return last
            if not last.real_mode_configured:
                return last
            time.sleep(poll_s)
        return last or self.status()

    def smoke_test(
        self,
        *,
        composite: bool = False,
        question: str | None = None,
    ) -> SmokeTestResult:
        status = self.status()
        if not status.real_mode_configured:
            return SmokeTestResult(
                ok=False,
                blocked=True,
                status="BLOCKED",
                error=status.message,
            )
        if not status.reachable:
            return SmokeTestResult(
                ok=False,
                blocked=True,
                status="BLOCKED",
                error=status.health_error or status.message,
            )
        if not status.model_loaded or status.health.get("status") != "ok":
            return SmokeTestResult(
                ok=False,
                blocked=True,
                status="BLOCKED",
                error="GeoChat model is not loaded yet.",
                response=status.health,
            )

        url = self._require_service_url()
        if composite:
            raw = build_evidence_composite_smoke()
            payload = {
                "model_id": self.config.model_id,
                "question": question
                or "What visible change occurred in this detected region between the two dates?",
                "image": {
                    "content_base64": base64.b64encode(raw).decode("ascii"),
                    "format": "png",
                    "filename": "evidence-composite-smoke.png",
                },
                "image_metadata": {
                    "image_id": "evidence-composite-smoke",
                    "modality": "optical",
                    "width": 512,
                    "height": 284,
                    "georeferenced": True,
                    "benchmark_dataset": False,
                },
                "parameters": {"max_new_tokens": 120, "temperature": 1.0, "do_sample": False},
            }
        else:
            from pathlib import Path

            smoke_png = (
                Path(__file__).resolve().parents[3]
                / "experiments"
                / "phase9b_geochat"
                / "assets"
                / "sentinel2_smoketest.png"
            )
            if not smoke_png.exists():
                return SmokeTestResult(
                    ok=False,
                    blocked=True,
                    status="BLOCKED",
                    error=f"Smoke PNG missing: {smoke_png}",
                )
            raw = smoke_png.read_bytes()
            payload = {
                "model_id": self.config.model_id,
                "question": question
                or "Describe the main land-cover types visible in this satellite image.",
                "image": {
                    "content_base64": base64.b64encode(raw).decode("ascii"),
                    "format": "png",
                    "filename": smoke_png.name,
                },
                "image_metadata": {
                    "image_id": "sentinel2-smoketest",
                    "modality": "optical",
                    "width": 504,
                    "height": 504,
                    "georeferenced": False,
                    "benchmark_dataset": True,
                },
                "parameters": {"max_new_tokens": 120, "temperature": 1.0, "do_sample": False},
            }

        try:
            response = httpx.post(
                f"{url}/v1/vqa",
                json=payload,
                timeout=max(self.config.timeout_s, 120.0),
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            return SmokeTestResult(
                ok=False,
                blocked=False,
                status="FAIL",
                error=str(exc),
                composite=composite,
            )

        answer = str(body.get("answer", "")).strip()
        model_name = str(body.get("model_name", ""))
        provider = str(body.get("provider", ""))
        lower_answer = answer.lower()
        if not answer:
            return SmokeTestResult(
                ok=False,
                blocked=False,
                status="FAIL",
                error="Empty answer from GeoChat service.",
                response=body,
                composite=composite,
            )
        if any(marker in lower_answer for marker in MOCK_MARKERS):
            return SmokeTestResult(
                ok=False,
                blocked=False,
                status="FAIL",
                error="Response appears to be a development mock.",
                answer=answer,
                response=body,
                composite=composite,
            )
        if model_name != self.config.model_id:
            return SmokeTestResult(
                ok=False,
                blocked=False,
                status="FAIL",
                error=f"Unexpected model_name: {model_name}",
                answer=answer,
                response=body,
                composite=composite,
            )
        if provider != "geochat_service":
            return SmokeTestResult(
                ok=False,
                blocked=False,
                status="FAIL",
                error=f"Unexpected provider: {provider}",
                answer=answer,
                response=body,
                composite=composite,
            )

        return SmokeTestResult(
            ok=True,
            blocked=False,
            status="PASS",
            answer=answer,
            model_name=model_name,
            provider=provider,
            response=body,
            composite=composite,
        )


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))
