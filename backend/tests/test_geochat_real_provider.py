"""Real GeoChat provider acceptance and no-fallback guards."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GEochat_ROOT = REPO_ROOT / "services" / "geochat"

# Capture opt-in real-service env at import/collection time before autouse fixtures run.
_REAL_SERVICE_TEST = os.environ.get("GEOCHAT_REAL_SERVICE_TEST", "").lower() == "true"
_REAL_SERVICE_URL = os.environ.get("GEOCHAT_SERVICE_URL")
_REAL_MODEL_ID = os.environ.get("GEOCHAT_MODEL_ID", "MBZUAI/geochat-7B")
_REAL_SERVICE_TIMEOUT_S = os.environ.get("GEOCHAT_SERVICE_TIMEOUT_S", "120")


def _import_geochat_dev():
    inserted = False
    geochat_root = str(GEochat_ROOT)
    if geochat_root not in sys.path:
        sys.path.insert(0, geochat_root)
        inserted = True
    try:
        from geochat_dev.acceptance import real_service_env_ready, run_real_provider_acceptance
        from geochat_dev.config import GeoChatDevConfig
    finally:
        if inserted:
            sys.path.remove(geochat_root)

    return real_service_env_ready, run_real_provider_acceptance, GeoChatDevConfig


@pytest.fixture
def upload_root(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(root))
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "8")
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.adapters.rsvlm.factory import get_geochat_vlm

    get_geochat_vlm.cache_clear()
    yield root
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


def test_factory_requires_service_url_for_real_provider(monkeypatch):
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "geochat_service")
    # Override backend/.env; delenv alone would fall back to the file value.
    monkeypatch.setenv("GEOCHAT_SERVICE_URL", "")
    from app.adapters.rsvlm.factory import get_geochat_vlm
    from app.core.config import get_settings
    from app.core.errors import SatQueryError

    get_settings.cache_clear()
    get_geochat_vlm.cache_clear()
    with pytest.raises(SatQueryError) as exc:
        get_geochat_vlm()
    assert exc.value.code == "geochat_service_misconfigured"
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


def test_factory_unknown_provider_is_misconfigured(monkeypatch):
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "unknown-provider")
    from app.adapters.rsvlm.factory import get_geochat_vlm
    from app.core.config import get_settings
    from app.core.errors import SatQueryError

    get_settings.cache_clear()
    get_geochat_vlm.cache_clear()
    with pytest.raises(SatQueryError) as exc:
        get_geochat_vlm()
    assert exc.value.code == "geochat_vqa_misconfigured"
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


def test_development_provider_is_not_real(upload_root):
    from app.adapters.rsvlm.factory import get_geochat_vlm
    from app.schemas.vqa import VQAProviderKind

    vlm = get_geochat_vlm()
    assert vlm.provider_kind == VQAProviderKind.DEVELOPMENT.value


def test_acceptance_blocked_without_live_service():
    _, run_real_provider_acceptance, GeoChatDevConfig = _import_geochat_dev()
    config = GeoChatDevConfig(
        provider="geochat_service",
        service_url="http://127.0.0.1:1",
        model_id="MBZUAI/geochat-7B",
        timeout_s=2.0,
        env_file=None,
        env_file_loaded=False,
    )
    result = run_real_provider_acceptance(config, include_satquery_adapter=False)
    assert result.status == "BLOCKED"


@pytest.mark.skipif(
    not _REAL_SERVICE_TEST,
    reason="Set GEOCHAT_REAL_SERVICE_TEST=true to run against a live GPU GeoChat service.",
)
def test_real_geochat_provider_acceptance():
    _, run_real_provider_acceptance, GeoChatDevConfig = _import_geochat_dev()
    if not _REAL_SERVICE_URL:
        pytest.skip("GEOCHAT_SERVICE_URL is required for real provider acceptance.")
    config = GeoChatDevConfig(
        provider="geochat_service",
        service_url=_REAL_SERVICE_URL.rstrip("/"),
        model_id=_REAL_MODEL_ID,
        timeout_s=float(_REAL_SERVICE_TIMEOUT_S),
        env_file=None,
        env_file_loaded=False,
    )
    result = run_real_provider_acceptance(config, include_satquery_adapter=True)
    assert result.status == "PASS", result.to_dict()
    providers = {
        check.payload.get("provider")
        for check in result.checks
        if check.payload and check.payload.get("provider")
    }
    assert "geochat_service" in providers or any(
        check.name == "satquery_adapter" and check.status == "PASS" for check in result.checks
    )


@pytest.mark.skipif(
    not _REAL_SERVICE_TEST,
    reason="Set GEOCHAT_REAL_SERVICE_TEST=true to run real region interpretation acceptance.",
)
@pytest.mark.asyncio
async def test_real_region_interpretation_acceptance(upload_root, monkeypatch):
    if not _REAL_SERVICE_URL:
        pytest.skip("GEOCHAT_SERVICE_URL is required.")
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.schemas.vqa import VQAProviderKind
    from tests.fixtures.rasters import write_bi_temporal_scene

    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "geochat_service")
    monkeypatch.setenv("GEOCHAT_SERVICE_URL", _REAL_SERVICE_URL.rstrip("/"))
    monkeypatch.setenv("GEOCHAT_MODEL_ID", _REAL_MODEL_ID)
    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "bi_temporal")
    from app.core.config import get_settings
    from app.adapters.rsvlm.factory import get_geochat_vlm

    get_settings.cache_clear()
    get_geochat_vlm.cache_clear()

    earlier_path = upload_root / "bt_before.tif"
    later_path = upload_root / "bt_after.tif"
    write_bi_temporal_scene(earlier_path, role="earlier", scenario="vegetation_loss")
    write_bi_temporal_scene(later_path, role="later", scenario="vegetation_loss")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async def upload(path, dt: str) -> str:
            with path.open("rb") as handle:
                res = await client.post(
                    "/api/v1/imagery/upload",
                    files={"file": (path.name, handle, "image/tiff")},
                    data={"modality": "multispectral", "acquisition_datetime": dt},
                )
            assert res.status_code == 200
            return res.json()["data"]["image"]["id"]

        earlier_id = await upload(earlier_path, "2023-01-01T00:00:00Z")
        later_id = await upload(later_path, "2024-01-01T00:00:00Z")
        query = await client.post(
            "/api/v1/query/submit",
            json={
                "query": "What changed between these two dates, and where did the change occur?",
                "earlier_image_id": earlier_id,
                "later_image_id": later_id,
            },
        )
        assert query.status_code == 200
        session_id = query.json()["data"]["session_id"]
        region_id = query.json()["data"]["result"]["evidence"][0]["id"]

        res = await client.post(
            f"/api/v1/query/{session_id}/regions/{region_id}/interpret",
            json={
                "question": "What visible change occurred in this detected region between the two dates?",
            },
        )
        assert res.status_code == 200, res.text
        interpretation = res.json()["data"]["interpretation"]
        assert interpretation["provider"] == VQAProviderKind.GEOCHAT_SERVICE.value
        assert interpretation["model_name"] == _REAL_MODEL_ID
        assert "development mock" not in interpretation["answer"].lower()
        assert "[development mock" not in interpretation["answer"].lower()
        assert interpretation["detector"] == "uploaded_bi_temporal"

    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


def test_real_service_env_ready_false_by_default(monkeypatch):
    monkeypatch.delenv("GEOCHAT_REAL_SERVICE_TEST", raising=False)
    monkeypatch.delenv("GEOCHAT_SERVICE_URL", raising=False)
    real_service_env_ready, _, _ = _import_geochat_dev()
    assert real_service_env_ready() is False
