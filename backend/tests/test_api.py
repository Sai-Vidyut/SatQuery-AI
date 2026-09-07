from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.domain import AOI, GeoJSONGeometry, QueryRequest


SAMPLE_AOI = AOI(
    geometry=GeoJSONGeometry(
        type="Polygon",
        coordinates=[
            [
                [77.59, 12.97],
                [77.61, 12.97],
                [77.61, 12.99],
                [77.59, 12.99],
                [77.59, 12.97],
            ]
        ],
    ),
    area_km2=4.8,
)

SAMPLE_QUERY = QueryRequest(
    query="Show me significant new construction.",
    aoi=SAMPLE_AOI,
    earlier_date=date(2024, 1, 12),
    later_date=date(2025, 3, 3),
)

SAMPLE_IMAGERY_FETCH = {
    "aoi": SAMPLE_AOI.model_dump(mode="json"),
    "start_date": "2024-01-12",
    "end_date": "2025-03-03",
}


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


@pytest.mark.asyncio
async def test_query_submit_and_trace(client):
    res = await client.post("/api/v1/query/submit", json=SAMPLE_QUERY.model_dump(mode="json"))
    assert res.status_code == 200
    body = res.json()["data"]
    session_id = body["session_id"]
    result = body["result"]
    assert result["status"] == "completed"
    assert len(result["evidence"]) >= 1
    assert result["mode"] == "development"

    trace_res = await client.get(f"/api/v1/query/{session_id}/trace")
    assert trace_res.status_code == 200
    trace = trace_res.json()["data"]
    assert len(trace) == 7
    assert all(s["status"] == "completed" for s in trace)
    tool_names = [s["tool_name"] for s in trace]
    assert tool_names == [
        "plan_query",
        "fetch_imagery",
        "detect_change",
        "analyze_semantics",
        "detect_sar_change",
        "fuse_evidence",
        "generate_evidence",
    ]


@pytest.mark.asyncio
async def test_invalid_aoi_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AOI(
            geometry=GeoJSONGeometry(type="Point", coordinates=[77.6, 12.98]),
        )


@pytest.mark.asyncio
async def test_detect_change_endpoint(client):
    res = await client.post("/api/v1/analysis/detect-change", json=SAMPLE_QUERY.model_dump(mode="json"))
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["raw_detection_count"] >= 1
    assert data["mode"] == "development"


@pytest.mark.asyncio
async def test_non_construction_query_skips_semantic_step(client):
    query = SAMPLE_QUERY.model_copy(update={"query": "Show spectral vegetation change."})
    res = await client.post("/api/v1/query/submit", json=query.model_dump(mode="json"))
    assert res.status_code == 200
    trace = res.json()["data"]["result"]["trace"]
    semantic_step = next(s for s in trace if s["tool_name"] == "analyze_semantics")
    assert "skipped" in semantic_step["summary"].lower()


@pytest.mark.asyncio
async def test_catalog_multimodal_language_rejected_in_development(client):
    query = SAMPLE_QUERY.model_copy(
        update={
            "query": (
                "Use the optical and SAR images together to identify "
                "built-up and water-covered regions."
            ),
            "demo_mode": True,
        }
    )
    res = await client.post("/api/v1/query/submit", json=query.model_dump(mode="json"))
    assert res.status_code == 422
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "catalog_sar_unsupported"
    assert "Cross-modal upload" in body["error"]["user_message"]


@pytest.mark.asyncio
async def test_evidence_metrics_from_detector_not_llm(client):
    res = await client.post("/api/v1/query/submit", json=SAMPLE_QUERY.model_dump(mode="json"))
    metrics = res.json()["data"]["result"]["metrics"]
    names = {m["name"] for m in metrics}
    assert "region_count" in names
    assert "detector" in names


@pytest.mark.asyncio
async def test_catalog_demo_mode_sets_demonstration_data_flag(client):
    query = SAMPLE_QUERY.model_copy(update={"demo_mode": True})
    res = await client.post("/api/v1/query/submit", json=query.model_dump(mode="json"))
    assert res.status_code == 200
    result = res.json()["data"]["result"]
    assert result["mode"] == "development"
    assert result["demonstration_data"] is True
    assert "DEMONSTRATION DATA" in result["answer"]


@pytest.mark.asyncio
async def test_catalog_development_provider_without_demo_mode_is_not_demonstration_data(client):
    res = await client.post("/api/v1/query/submit", json=SAMPLE_QUERY.model_dump(mode="json"))
    assert res.status_code == 200
    result = res.json()["data"]["result"]
    assert result["mode"] == "development"
    assert result["demonstration_data"] is False
    assert "MOCK PROVIDERS" in result["answer"]
    assert "DEMONSTRATION DATA" not in result["answer"]


@pytest.mark.asyncio
async def test_fetch_imagery_success_development_provider(client):
    res = await client.post("/api/v1/imagery/fetch", json=SAMPLE_IMAGERY_FETCH)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["source"] == "satquery-development-imagery"
    assert data["mode"] == "development"
    assert data["sensor"] == "sentinel-2"
    assert len(data["scenes"]) == 2
    assert all(scene["scene_id"].startswith("dev-") for scene in data["scenes"])
    assert data["spatial"]["bbox"] == [77.59, 12.97, 77.61, 12.99]
    assert data["provider_metadata"]["demonstration_data"] is True
    assert "DEMONSTRATION DATA" in data["message"]


@pytest.mark.asyncio
async def test_fetch_imagery_rejects_missing_request_body(client):
    res = await client.post("/api/v1/imagery/fetch", json={})
    assert res.status_code == 422
    body = res.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_fetch_imagery_rejects_invalid_date_range(client):
    payload = {
        **SAMPLE_IMAGERY_FETCH,
        "start_date": "2025-03-03",
        "end_date": "2024-01-12",
    }
    res = await client.post("/api/v1/imagery/fetch", json=payload)
    assert res.status_code == 422
    body = res.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_fetch_imagery_rejects_invalid_aoi_geometry(client):
    payload = {
        **SAMPLE_IMAGERY_FETCH,
        "aoi": {"geometry": {"type": "Point", "coordinates": [77.6, 12.98]}},
    }
    res = await client.post("/api/v1/imagery/fetch", json=payload)
    assert res.status_code == 422
    body = res.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_fetch_imagery_returns_structured_provider_error(client, monkeypatch):
    from app.adapters.imagery.development import DevelopmentImageryProvider
    from app.core.errors import SatQueryError

    async def fail_fetch(self, _request):
        raise SatQueryError(
            "no_imagery_found",
            "No scenes matched the request.",
            status_code=404,
        )

    monkeypatch.setattr(DevelopmentImageryProvider, "fetch", fail_fetch)

    res = await client.post("/api/v1/imagery/fetch", json=SAMPLE_IMAGERY_FETCH)
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "no_imagery_found"
    assert body["error"]["user_message"]
    assert "imagery" in body["error"]["user_message"].lower()


@pytest.mark.asyncio
async def test_query_result_matches_submit_response(client):
    submit = await client.post(
        "/api/v1/query/submit",
        json=SAMPLE_QUERY.model_dump(mode="json"),
    )
    assert submit.status_code == 200
    submit_data = submit.json()["data"]
    session_id = submit_data["session_id"]
    submit_result = submit_data["result"]

    res = await client.get(f"/api/v1/query/{session_id}/result")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    fetched = body["data"]
    assert fetched["session_id"] == session_id
    assert fetched["status"] == submit_result["status"]
    assert fetched["answer"] == submit_result["answer"]
    assert fetched["mode"] == submit_result["mode"]
    assert len(fetched["evidence"]) == len(submit_result["evidence"])
    assert fetched["evidence"][0]["id"] == submit_result["evidence"][0]["id"]
    assert len(fetched["trace"]) == len(submit_result["trace"])


@pytest.mark.asyncio
async def test_query_result_not_found_for_unknown_session(client):
    res = await client.get("/api/v1/query/00000000-0000-0000-0000-000000000000/result")
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "session_not_found"
    assert body["error"]["user_message"]


@pytest.mark.asyncio
async def test_query_result_not_found_before_result_exists(client):
    from app.services.query_controller import query_controller

    session_id = query_controller._store.create()
    res = await client.get(f"/api/v1/query/{session_id}/result")
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "session_not_found"
    assert "No result for session" in body["error"]["message"]
