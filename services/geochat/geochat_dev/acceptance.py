"""Real GeoChat provider acceptance checks — opt-in only, never silent fallback."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Literal

from geochat_dev.client import GeoChatDevClient, MOCK_MARKERS
from geochat_dev.composite import build_evidence_composite_smoke
from geochat_dev.config import GeoChatDevConfig, load_config


AcceptanceStatus = Literal["PASS", "BLOCKED", "FAIL"]


@dataclass
class AcceptanceCheck:
    name: str
    status: AcceptanceStatus
    detail: str
    payload: dict[str, Any] | None = None


@dataclass
class AcceptanceResult:
    status: AcceptanceStatus
    checks: list[AcceptanceCheck] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status,
                    "detail": check.detail,
                    "payload": check.payload,
                }
                for check in self.checks
            ],
        }


def _finalize(checks: list[AcceptanceCheck]) -> AcceptanceResult:
    if any(check.status == "FAIL" for check in checks):
        return AcceptanceResult(
            status="FAIL",
            checks=checks,
            message="Real GeoChat provider acceptance failed.",
        )
    if any(check.status == "BLOCKED" for check in checks):
        return AcceptanceResult(
            status="BLOCKED",
            checks=checks,
            message="Real GeoChat provider acceptance blocked — service unavailable.",
        )
    return AcceptanceResult(
        status="PASS",
        checks=checks,
        message="Real GeoChat provider acceptance passed.",
    )


def run_real_provider_acceptance(
    config: GeoChatDevConfig | None = None,
    *,
    include_satquery_adapter: bool = True,
) -> AcceptanceResult:
    """Run deterministic real-provider acceptance without silent development fallback."""
    cfg = config or load_config()
    client = GeoChatDevClient(cfg)
    checks: list[AcceptanceCheck] = []

    if cfg.provider != "geochat_service":
        checks.append(
            AcceptanceCheck(
                name="provider_mode",
                status="BLOCKED",
                detail=(
                    "GEOCHAT_VQA_PROVIDER is not geochat_service. "
                    "Set real mode before running acceptance."
                ),
            )
        )
        return _finalize(checks)

    if not cfg.service_url:
        checks.append(
            AcceptanceCheck(
                name="service_url",
                status="BLOCKED",
                detail="GEOCHAT_SERVICE_URL is not configured.",
            )
        )
        return _finalize(checks)

    status = client.status()
    if not status.reachable:
        checks.append(
            AcceptanceCheck(
                name="service_health",
                status="BLOCKED",
                detail=status.health_error or status.message,
            )
        )
        return _finalize(checks)

    health = status.health or {}
    checks.append(
        AcceptanceCheck(
            name="service_health",
            status="PASS" if health.get("status") == "ok" else "BLOCKED",
            detail=f"health.status={health.get('status')}",
            payload=health,
        )
    )
    checks.append(
        AcceptanceCheck(
            name="model_loaded",
            status="PASS" if health.get("model_loaded") else "BLOCKED",
            detail=f"model_loaded={health.get('model_loaded')}",
            payload={"startup_state": health.get("startup_state")},
        )
    )
    checks.append(
        AcceptanceCheck(
            name="model_metadata",
            status="PASS"
            if health.get("model_name") == cfg.model_id and health.get("provider") == "geochat_service"
            else "FAIL",
            detail=f"model_name={health.get('model_name')} provider={health.get('provider')}",
        )
    )
    if status.tunnel_public:
        checks.append(
            AcceptanceCheck(
                name="public_tunnel",
                status="PASS",
                detail=f"Public tunnel reachable at {status.redacted_service_url}",
            )
        )

    smoke = client.smoke_test(composite=True)
    checks.append(
        AcceptanceCheck(
            name="composite_vqa",
            status=smoke.status,
            detail=smoke.error or (smoke.answer[:160] + "…" if smoke.answer and len(smoke.answer) > 160 else smoke.answer or ""),
            payload=smoke.response,
        )
    )

    if include_satquery_adapter and smoke.status == "PASS":
        adapter_check = _run_satquery_adapter_check(cfg)
        checks.append(adapter_check)

    return _finalize(checks)


def _run_satquery_adapter_check(cfg: GeoChatDevConfig) -> AcceptanceCheck:
    try:
        from app.adapters.rsvlm.geochat_service import GeoChatServiceVLM
        from app.schemas.vqa import GeoChatVQAParameters
    except ImportError:
        return AcceptanceCheck(
            name="satquery_adapter",
            status="BLOCKED",
            detail="SatQuery backend package not importable from this environment.",
        )

    composite = build_evidence_composite_smoke()
    prompt = (
        "A change detection system has ALREADY identified this region.\n"
        "Do NOT decide whether change exists.\n"
        "LEFT panel = BEFORE. RIGHT panel = AFTER.\n"
        "User question: What visible change occurred in this detected region between the two dates?"
    )

    async def _call() -> Any:
        vlm = GeoChatServiceVLM(cfg.service_url or "", cfg.model_id)
        return await vlm.run_composite_vqa(
            composite_png=composite,
            question=prompt,
            parameters=GeoChatVQAParameters(max_new_tokens=120),
            composite_image_id="acceptance-smoke",
            modality="optical",
        )

    try:
        result = asyncio.run(_call())
    except Exception as exc:
        return AcceptanceCheck(
            name="satquery_adapter",
            status="FAIL",
            detail=str(exc),
        )

    lower = result.answer.lower()
    if not result.answer.strip():
        return AcceptanceCheck(
            name="satquery_adapter",
            status="FAIL",
            detail="SatQuery adapter received an empty answer.",
        )
    if any(marker in lower for marker in MOCK_MARKERS):
        return AcceptanceCheck(
            name="satquery_adapter",
            status="FAIL",
            detail="SatQuery adapter received a development mock answer.",
        )
    if result.provider.value != "geochat_service":
        return AcceptanceCheck(
            name="satquery_adapter",
            status="FAIL",
            detail=f"Unexpected provider from adapter: {result.provider.value}",
        )

    return AcceptanceCheck(
        name="satquery_adapter",
        status="PASS",
        detail=(
            f"provider={result.provider.value} model={result.model_name} "
            f"answer_len={len(result.answer)}"
        ),
        payload={
            "provider": result.provider.value,
            "model_name": result.model_name,
            "model_version": result.model_version,
            "provenance": result.provenance,
        },
    )


def real_service_env_ready() -> bool:
    return (
        os.environ.get("GEOCHAT_REAL_SERVICE_TEST", "").lower() == "true"
        and bool(os.environ.get("GEOCHAT_SERVICE_URL"))
    )
