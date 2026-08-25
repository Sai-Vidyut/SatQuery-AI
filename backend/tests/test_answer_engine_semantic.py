from __future__ import annotations

from datetime import date

import pytest

from app.schemas.domain import (
    AOI,
    DataMode,
    EvidenceRegion,
    GenerateEvidenceOutput,
    GeoJSONGeometry,
    QueryRequest,
)
from app.services.answer_engine import AnswerEngine
from app.services.query_profiles import BUILDING_CONSTRUCTION_PROFILE


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
)


def _evidence_with_candidates(count: int) -> GenerateEvidenceOutput:
    regions = [
        EvidenceRegion(
            id="change-region-01",
            geometry=SAMPLE_AOI.geometry,
            type="spectral_change",
            confidence=0.6,
            metrics=[],
            source="earth_engine_cva",
            metadata={"claim_type": "none"},
        )
    ]
    for i in range(count):
        regions.append(
            EvidenceRegion(
                id=f"semantic-{i}",
                geometry=SAMPLE_AOI.geometry,
                type="semantic_evidence",
                confidence=0.5,
                metrics=[],
                source="development_semantic_analyzer",
                metadata={"claim_type": "construction_candidate"},
            )
        )
    return GenerateEvidenceOutput(regions=regions, metrics=[], confidence=0.55)


def test_answer_engine_never_claims_confirmed_construction():
    engine = AnswerEngine()
    request = QueryRequest(
        query="Show me significant new construction.",
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 1, 1),
        later_date=date(2025, 1, 1),
    )
    answer = engine.compose(
        request,
        _evidence_with_candidates(2),
        DataMode.DEVELOPMENT,
        analysis_profile=BUILDING_CONSTRUCTION_PROFILE,
    )
    assert "construction candidate" in answer.lower()
    assert "confirmed" not in answer.lower()
    assert "new buildings" not in answer.lower()


def test_answer_engine_cva_only_language():
    engine = AnswerEngine()
    request = QueryRequest(
        query="What changed?",
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 1, 1),
        later_date=date(2025, 1, 1),
    )
    evidence = GenerateEvidenceOutput(
        regions=[
            EvidenceRegion(
                id="change-region-01",
                geometry=SAMPLE_AOI.geometry,
                type="spectral_change",
                confidence=0.6,
                metrics=[],
                source="earth_engine_cva",
                metadata={"claim_type": "none"},
            )
        ],
        metrics=[],
        confidence=0.6,
    )
    answer = engine.compose(request, evidence, DataMode.DEVELOPMENT, analysis_profile=None)
    assert "spectral change" in answer.lower()
    assert "construction candidate" not in answer.lower()
