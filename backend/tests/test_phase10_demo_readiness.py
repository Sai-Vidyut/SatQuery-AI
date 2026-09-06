"""Phase 10 — demo readiness, fallback policy, answer consistency, and error UX."""

from __future__ import annotations

from datetime import date

import pytest

from app.adapters.imagery.earth_engine.composite import (
    FALLBACK_POLICY_VERSION,
    build_composite_epochs,
    select_scenes_for_composite,
    select_scenes_for_composite_with_fallback,
)
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.core.errors import SatQueryError
from app.core.user_errors import user_facing_message
from app.schemas.change_domain import ChangeDomain, ClaimStrength
from app.schemas.domain import (
    AOI,
    DataMode,
    EvidenceRegion,
    GenerateEvidenceOutput,
    GeoJSONGeometry,
    Metric,
    QueryRequest,
)
from app.services.answer_engine import AnswerEngine
from app.services.change_domain import compose_domain_answer_clause, is_water_direction_ambiguous
from app.tools.evidence.fuse_evidence import FuseEvidenceTool
from app.schemas.domain import ChangeDetectionOutput, FuseEvidenceInput, SemanticAnalysisOutput


def _scene(scene_id: str, acq: date, cloud: float = 8.0) -> SceneCandidate:
    return SceneCandidate(
        scene_id=scene_id,
        platform_id=f"COPERNICUS/S2_SR_HARMONIZED/{scene_id}",
        acquisition_date=acq,
        cloud_cover_percent=cloud,
        metadata={},
    )


def _aoi() -> AOI:
    return AOI(
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [77.56, 12.94],
                    [77.60, 12.94],
                    [77.60, 12.98],
                    [77.56, 12.98],
                    [77.56, 12.94],
                ]
            ],
        )
    )


def _region(region_id: str = "r-1") -> EvidenceRegion:
    return EvidenceRegion(
        id=region_id,
        type="spectral_change",
        geometry=_aoi().geometry,
        confidence=0.72,
        source="test",
        metrics=[Metric(name="area_m2", value=5000.0, unit="m²", source="test")],
        metadata={"evidence_type": "spectral_change", "claim_type": "vegetation_loss_candidate"},
    )


def test_tier1_composite_window_unchanged():
    anchor = date(2024, 6, 15)
    candidates = [_scene("jun1", date(2024, 6, 5)), _scene("jun2", date(2024, 6, 20))]
    scenes, w_start, w_end, fb = select_scenes_for_composite_with_fallback(
        candidates, anchor, epoch_label="T1"
    )
    assert len(scenes) == 2
    assert fb["tier"] == 1
    assert fb["fallback_used"] is False
    assert w_start == date(2024, 5, 31)
    assert w_end == date(2024, 6, 30)


def test_tier2_widens_window_when_tier1_empty():
    anchor = date(2024, 6, 15)
    candidates = [_scene("apr", date(2024, 4, 20)), _scene("aug", date(2024, 8, 10))]
    scenes, w_start, w_end, fb = select_scenes_for_composite_with_fallback(
        candidates, anchor, epoch_label="T1"
    )
    assert len(scenes) >= 1
    assert fb["tier"] == 2
    assert fb["fallback_used"] is True
    assert fb["policy_decision"] == "tier_2_widened_window"
    assert w_start < date(2024, 5, 31)


def test_tier3_nearest_scene_when_max_window_empty():
    anchor = date(2024, 6, 15)
    candidates = [_scene("far", date(2023, 1, 10))]
    scenes, w_start, w_end, fb = select_scenes_for_composite_with_fallback(
        candidates, anchor, epoch_label="T1"
    )
    assert len(scenes) == 1
    assert fb["tier"] == 3
    assert fb["fallback_used"] is True
    assert fb["policy_decision"] == "tier_3_nearest_scene"
    assert w_start == date(2023, 1, 10)


def test_strict_select_scenes_raises_on_empty_tier1():
    with pytest.raises(SatQueryError) as exc:
        select_scenes_for_composite([], date(2024, 6, 1), epoch_label="T1")
    assert exc.value.code == "no_imagery_found"


def test_build_composite_epochs_records_fallback_provenance():
    candidates = [
        _scene("t1far", date(2018, 3, 10)),
        _scene("t2a", date(2024, 6, 5)),
        _scene("t2b", date(2024, 6, 22)),
    ]
    scenes, prov = build_composite_epochs(
        candidates,
        requested_start=date(2018, 6, 1),
        requested_end=date(2024, 6, 1),
    )
    assert len(scenes) == 2
    assert prov["fallback_policy"] == FALLBACK_POLICY_VERSION
    assert scenes[0].acquisition_date == date(2018, 6, 1)
    assert prov["t1"]["fallback"]["fallback_used"] is True


def test_water_direction_ambiguous_on_expansion_hint():
    assert is_water_direction_ambiguous(
        ChangeDomain.WATER_SHRINKAGE,
        direction_hint="water_expansion",
        strength=ClaimStrength.SUPPORTED,
    )


def test_water_ambiguity_answer_wording():
    clause = compose_domain_answer_clause(
        ChangeDomain.WATER_SHRINKAGE,
        strength=ClaimStrength.SUPPORTED,
        direction_hint="water_expansion",
        primary_index="ndwi",
        region_count=3,
    )
    assert "inconclusive" in clause.lower()
    assert "shrank" not in clause.lower()
    assert "expanded" not in clause.lower()


def test_domain_answer_aligns_with_regions_when_detected():
    clause = compose_domain_answer_clause(
        ChangeDomain.DEFORESTATION,
        strength=ClaimStrength.DETECTED,
        direction_hint="vegetation_loss",
        primary_index="ndvi",
        region_count=5,
    )
    assert "5 mapped region" in clause


@pytest.mark.asyncio
async def test_fuse_evidence_passes_detector_metadata():
    tool = FuseEvidenceTool()
    cva = ChangeDetectionOutput(
        regions=[_region()],
        raw_detection_count=1,
        detector="earth_engine_cva",
        mode=DataMode.EARTH_ENGINE,
        detector_metadata={
            "primary_index": "ndvi",
            "change_direction_hint": "vegetation_loss",
            "confidence_kind": "histogram_separability",
            "area_ha": 12.5,
        },
    )
    out = await tool.execute(
        FuseEvidenceInput(
            cva_detections=cva,
            semantic=SemanticAnalysisOutput(
                regions=[], analyzer="none", mode=DataMode.DEVELOPMENT
            ),
            sar_detections=None,
        )
    )
    assert out.fusion_metadata["detector_metadata"]["primary_index"] == "ndvi"
    assert out.fusion_metadata["confidence_kind"] == "histogram_separability"


def test_answer_engine_domain_consistency_with_regions():
    engine = AnswerEngine()
    request = QueryRequest(
        query="Show deforestation in this AOI.",
        aoi=_aoi(),
        earlier_date=date(2019, 8, 1),
        later_date=date(2023, 8, 1),
    )
    evidence = GenerateEvidenceOutput(
        regions=[_region()],
        confidence=0.71,
        metrics=[],
    )
    answer = engine.compose(
        request,
        evidence,
        DataMode.EARTH_ENGINE,
        change_domain=ChangeDomain.DEFORESTATION,
        fusion_metadata={
            "detector_metadata": {
                "primary_index": "ndvi",
                "change_direction_hint": "vegetation_loss",
                "area_ha": 10.0,
            }
        },
    )
    assert "1 domain candidate region" in answer or "1 mapped region" in answer
    assert "separability" in answer.lower()
    assert "event probability" in answer.lower()


def test_demo_mode_answer_labels_demonstration_data():
    engine = AnswerEngine()
    request = QueryRequest(
        query="Show urban expansion.",
        aoi=_aoi(),
        earlier_date=date(2018, 6, 1),
        later_date=date(2024, 6, 1),
        demo_mode=True,
    )
    evidence = GenerateEvidenceOutput(regions=[_region()], confidence=0.6, metrics=[])
    answer = engine.compose(
        request,
        evidence,
        DataMode.DEVELOPMENT,
        change_domain=ChangeDomain.URBAN_EXPANSION,
        fusion_metadata={"detector_metadata": {"primary_index": "ndbi"}},
    )
    assert "DEMONSTRATION DATA" in answer


def test_user_facing_error_messages():
    assert "imagery" in user_facing_message("no_imagery_found").lower()
    assert user_facing_message("unknown_code", "fallback") == "fallback"


def test_query_request_accepts_demo_mode():
    req = QueryRequest(
        query="Show mining activity.",
        aoi=_aoi(),
        earlier_date=date(2017, 6, 1),
        later_date=date(2023, 6, 1),
        demo_mode=True,
    )
    assert req.demo_mode is True
