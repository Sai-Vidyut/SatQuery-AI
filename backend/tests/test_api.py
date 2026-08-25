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
async def test_evidence_metrics_from_detector_not_llm(client):
    res = await client.post("/api/v1/query/submit", json=SAMPLE_QUERY.model_dump(mode="json"))
    metrics = res.json()["data"]["result"]["metrics"]
    names = {m["name"] for m in metrics}
    assert "region_count" in names
    assert "detector" in names
