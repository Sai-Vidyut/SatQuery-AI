"""Tests for deterministic bi-temporal region inspection priority ranking."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.main import app
from app.schemas.domain import EvidenceRegion, GeoJSONGeometry, Metric
from app.services.region_ranking import (
    compute_priority_score,
    priority_label_for_score,
    rank_bi_temporal_regions,
    region_ranking_service,
)
from app.services.session_store import session_store
from tests.fixtures.rasters import write_bi_temporal_scene


def _region(
    region_id: str,
    *,
    confidence: float = 0.9,
    area_m2: float = 1000.0,
    direction_hint: str | None = "vegetation_loss",
    claim_type: str = "none",
) -> EvidenceRegion:
    return EvidenceRegion(
        id=region_id,
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[[[77.0, 12.0], [77.1, 12.0], [77.1, 12.1], [77.0, 12.1], [77.0, 12.0]]],
        ),
        type="spectral_change",
        confidence=confidence,
        source="uploaded_bi_temporal",
        metrics=[
            Metric(name="area_m2", value=area_m2, unit="m²", source="uploaded_bi_temporal"),
            Metric(
                name="histogram_confidence",
                value=confidence,
                unit="ratio",
                source="uploaded_bi_temporal",
            ),
        ],
        metadata={
            "confidence_kind": "histogram_separability",
            "change_direction_hint": direction_hint,
            "claim_type": claim_type,
            "evidence_type": "spectral_change",
        },
    )


@pytest.fixture
def upload_root(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(root))
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "8")
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "development")
    monkeypatch.setenv("GEOCHAT_SERVICE_URL", "")
    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "bi_temporal")
    get_settings.cache_clear()
    from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
    from app.adapters.rsvlm.factory import get_geochat_vlm
    from app.storage.factory import get_image_storage, get_metadata_registry

    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    get_uploaded_imagery_provider.cache_clear()
    get_geochat_vlm.cache_clear()
    session_store._conversations.clear()
    session_store._interpretations.clear()
    yield root
    session_store._conversations.clear()
    session_store._interpretations.clear()
    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    get_uploaded_imagery_provider.cache_clear()
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
async def client(upload_root):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _submit_bi_temporal(client: AsyncClient, upload_root) -> tuple[str, list[dict]]:
    earlier_path = upload_root / "bt_before.tif"
    later_path = upload_root / "bt_after.tif"
    write_bi_temporal_scene(earlier_path, role="earlier", scenario="vegetation_loss")
    write_bi_temporal_scene(later_path, role="later", scenario="vegetation_loss")

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
    payload = query.json()["data"]
    return payload["session_id"], payload["result"]["evidence"]


@pytest.mark.asyncio
async def test_ranked_regions_valid_session(client, upload_root):
    session_id, evidence = await _submit_bi_temporal(client, upload_root)
    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["task"] == "bi_temporal_region_ranking"
    assert body["session_id"] == session_id
    assert body["detector"] == "uploaded_bi_temporal"
    assert len(body["regions"]) == len(evidence)


@pytest.mark.asyncio
async def test_ranked_regions_have_contiguous_ranks(client, upload_root):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    ranks = [item["rank"] for item in res.json()["data"]["regions"]]
    assert ranks == list(range(1, len(ranks) + 1))


@pytest.mark.asyncio
async def test_ranked_regions_sorted_descending(client, upload_root):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    scores = [item["priority_score"] for item in res.json()["data"]["regions"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_priority_labels_are_deterministic(client, upload_root):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    first = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    second = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    labels_first = [item["priority_label"] for item in first.json()["data"]["regions"]]
    labels_second = [item["priority_label"] for item in second.json()["data"]["regions"]]
    assert labels_first == labels_second
    assert all(label in {"high", "medium", "low"} for label in labels_first)


@pytest.mark.asyncio
async def test_repeated_calls_are_identical(client, upload_root):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    first = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    second = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    assert first.json()["data"] == second.json()["data"]


@pytest.mark.asyncio
async def test_authoritative_region_ids_preserved(client, upload_root):
    session_id, evidence = await _submit_bi_temporal(client, upload_root)
    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    ranked_ids = {item["region_id"] for item in res.json()["data"]["regions"]}
    assert ranked_ids == {region["id"] for region in evidence}


@pytest.mark.asyncio
async def test_authoritative_confidence_preserved(client, upload_root):
    session_id, evidence = await _submit_bi_temporal(client, upload_root)
    by_id = {region["id"]: region for region in evidence}
    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    for item in res.json()["data"]["regions"]:
        assert item["confidence"] == by_id[item["region_id"]]["confidence"]


@pytest.mark.asyncio
async def test_authoritative_confidence_kind_preserved(client, upload_root):
    session_id, evidence = await _submit_bi_temporal(client, upload_root)
    by_id = {region["id"]: region for region in evidence}
    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    for item in res.json()["data"]["regions"]:
        assert item["confidence_kind"] == by_id[item["region_id"]]["metadata"]["confidence_kind"]


@pytest.mark.asyncio
async def test_authoritative_direction_hint_preserved(client, upload_root):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    result = (await client.get(f"/api/v1/query/{session_id}/result")).json()["data"]
    hint = result["bi_temporal_change"]["detector_summary"]["change_direction_hint"]
    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    for item in res.json()["data"]["regions"]:
        assert item["change_direction_hint"] == hint


@pytest.mark.asyncio
async def test_ranking_does_not_mutate_result(client, upload_root):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    before = await client.get(f"/api/v1/query/{session_id}/result")
    evidence_before = before.json()["data"]["evidence"]
    trace_before = (await client.get(f"/api/v1/query/{session_id}/trace")).json()["data"]

    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    assert res.status_code == 200

    after = await client.get(f"/api/v1/query/{session_id}/result")
    trace_after = (await client.get(f"/api/v1/query/{session_id}/trace")).json()["data"]
    assert after.json()["data"]["evidence"] == evidence_before
    assert trace_after == trace_before


@pytest.mark.asyncio
async def test_unknown_session(client):
    res = await client.get(
        "/api/v1/query/00000000-0000-0000-0000-000000000000/regions/ranked"
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "session_not_found"


@pytest.mark.asyncio
async def test_non_bi_temporal_session(client, upload_root):
    path = upload_root / "single.tif"
    write_bi_temporal_scene(path, role="earlier", scenario="vegetation_loss")
    with path.open("rb") as handle:
        upload = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("single.tif", handle, "image/tiff")},
            data={"modality": "multispectral"},
        )
    image_id = upload.json()["data"]["image"]["id"]
    query = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe this scene.", "image_id": image_id},
    )
    session_id = query.json()["data"]["session_id"]
    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "not_bi_temporal_session"


@pytest.mark.asyncio
async def test_zero_region_session_returns_empty_ranking(client, upload_root, monkeypatch):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    session = session_store.get(session_id)
    assert session and session.result
    session.result.evidence = []

    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    assert res.status_code == 200
    assert res.json()["data"]["regions"] == []


@pytest.mark.asyncio
async def test_no_geochat_invocation(client, upload_root, monkeypatch):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    mock_vqa = AsyncMock()
    monkeypatch.setattr(
        "app.adapters.rsvlm.development.DevelopmentGeoChatVLM.run_composite_vqa",
        mock_vqa,
    )
    res = await client.get(f"/api/v1/query/{session_id}/regions/ranked")
    assert res.status_code == 200
    mock_vqa.assert_not_called()


def test_compute_priority_score_uses_existing_signals_only():
    region = _region("change-region-01", confidence=0.8, area_m2=500.0)
    score = compute_priority_score(
        region,
        total_region_area_m2=1000.0,
        direction_hint="vegetation_loss",
    )
    assert 0.0 <= score <= 1.0
    assert score == compute_priority_score(
        region,
        total_region_area_m2=1000.0,
        direction_hint="vegetation_loss",
    )


def test_missing_optional_metrics_default_area_share_to_zero():
    region = EvidenceRegion(
        id="change-region-01",
        geometry=GeoJSONGeometry(type="Polygon", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]),
        confidence=0.7,
        source="uploaded_bi_temporal",
        metadata={"claim_type": "none"},
    )
    score = compute_priority_score(region, total_region_area_m2=0.0, direction_hint=None)
    assert score == round(0.45 * 0.7, 4)


def test_normalization_edge_case_single_region_full_area_share():
    region = _region("change-region-01", area_m2=2500.0, confidence=1.0)
    score = compute_priority_score(
        region,
        total_region_area_m2=2500.0,
        direction_hint="vegetation_loss",
    )
    assert score == round(0.45 * 1.0 + 0.25 * 1.0 + 0.20 * 1.0 + 0.10 * 0.0, 4)


def test_equal_score_regions_ordered_deterministically():
    regions = [
        _region("change-region-02", area_m2=1000.0, confidence=0.8),
        _region("change-region-01", area_m2=1000.0, confidence=0.8),
    ]
    ranking = rank_bi_temporal_regions(
        session_id="session-1",
        detector="uploaded_bi_temporal",
        regions=regions,
    )
    assert [item.region_id for item in ranking.regions] == ["change-region-01", "change-region-02"]


def test_larger_area_does_not_automatically_dominate_when_confidence_differs():
    low_area_high_conf = _region("change-region-01", area_m2=50.0, confidence=0.99)
    high_area_low_conf = _region("change-region-02", area_m2=5000.0, confidence=0.40)
    ranking = rank_bi_temporal_regions(
        session_id="session-1",
        detector="uploaded_bi_temporal",
        regions=[high_area_low_conf, low_area_high_conf],
    )
    assert ranking.regions[0].region_id == "change-region-01"


def test_tie_breaker_uses_area_then_region_id():
    regions = [
        _region("change-region-02", area_m2=800.0, confidence=0.75, direction_hint="no_change"),
        _region("change-region-01", area_m2=1200.0, confidence=0.75, direction_hint="no_change"),
    ]
    ranking = rank_bi_temporal_regions(
        session_id="session-1",
        detector="uploaded_bi_temporal",
        regions=regions,
    )
    assert ranking.regions[0].region_id == "change-region-01"
    assert ranking.regions[1].region_id == "change-region-02"


def test_priority_label_thresholds():
    assert priority_label_for_score(0.75) == "high"
    assert priority_label_for_score(0.50) == "medium"
    assert priority_label_for_score(0.20) == "low"


def test_rank_bi_temporal_regions_preserves_metrics():
    region = _region("change-region-01")
    ranking = rank_bi_temporal_regions(
        session_id="session-1",
        detector="uploaded_bi_temporal",
        regions=[region],
    )
    assert ranking.regions[0].metrics == region.metrics


def test_service_unknown_session():
    with pytest.raises(SatQueryError) as exc:
        region_ranking_service.rank_session_regions("00000000-0000-0000-0000-000000000000")
    assert exc.value.code == "session_not_found"
