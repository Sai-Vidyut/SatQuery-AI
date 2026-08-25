from __future__ import annotations

from app.adapters.semantic.base import SemanticAnalyzer
from app.schemas.domain import (
    DataMode,
    EvidenceRegion,
    GeoJSONGeometry,
    Metric,
    SemanticAnalysisInput,
    SemanticAnalysisOutput,
    SemanticClaim,
)

SEMANTIC_POLICY_VERSION = "1.0.0"
ANALYZER_NAME = "development_semantic_analyzer"
SUPPORTED_CLAIMS = ["construction_candidate", "new_built_area"]


def _bbox_from_ring(coords: list) -> tuple[float, float, float, float]:
    ring = coords[0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return min(lons), min(lats), max(lons), max(lats)


def _shrink_bbox(
    bbox: tuple[float, float, float, float],
    factor: float = 0.3,
) -> list[list[float]]:
    min_lon, min_lat, max_lon, max_lat = bbox
    width = max_lon - min_lon
    height = max_lat - min_lat
    cx = (min_lon + max_lon) / 2
    cy = (min_lat + max_lat) / 2
    w = width * factor
    h = height * factor
    return [
        [cx - w / 2, cy - h / 2],
        [cx + w / 2, cy - h / 2],
        [cx + w / 2, cy + h / 2],
        [cx - w / 2, cy + h / 2],
        [cx - w / 2, cy - h / 2],
    ]


class DevelopmentSemanticAnalyzer(SemanticAnalyzer):
    """
    Deterministic semantic candidates for development mode.
    Explicitly labeled — never masquerades as production evidence.
    """

    @property
    def name(self) -> str:
        return ANALYZER_NAME

    @property
    def supported_claims(self) -> list[str]:
        return list(SUPPORTED_CLAIMS)

    async def analyze(self, payload: SemanticAnalysisInput) -> SemanticAnalysisOutput:
        if not payload.change_regions:
            return SemanticAnalysisOutput(
                regions=[],
                claims=[],
                analyzer=self.name,
                mode=DataMode.DEVELOPMENT,
                analyzer_metadata={
                    "semantic_policy": SEMANTIC_POLICY_VERSION,
                    "analysis_profile": payload.analysis_profile,
                    "message": "Development semantic adapter — no CVA regions to evaluate.",
                },
            )

        regions: list[EvidenceRegion] = []
        claims: list[SemanticClaim] = []

        for idx, parent in enumerate(payload.change_regions[:2]):
            bbox = _bbox_from_ring(parent.geometry.coordinates)
            poly = _shrink_bbox(bbox)
            semantic_confidence = round(min(parent.confidence, 0.55), 3)
            claim_type = "construction_candidate" if idx == 0 else "new_built_area"
            region_id = f"semantic-candidate-{idx + 1:02d}"

            region = EvidenceRegion(
                id=region_id,
                geometry=GeoJSONGeometry(type="Polygon", coordinates=[poly]),
                type="semantic_evidence",
                confidence=semantic_confidence,
                metrics=[
                    Metric(
                        name="delta_built_probability",
                        value=0.18,
                        unit="probability",
                        source=ANALYZER_NAME,
                    ),
                    Metric(
                        name="overlap_fraction",
                        value=0.65,
                        unit="ratio",
                        source=ANALYZER_NAME,
                    ),
                ],
                source=ANALYZER_NAME,
                metadata={
                    "claim_type": claim_type,
                    "provenance_chain": [parent.source, ANALYZER_NAME],
                    "parent_region_id": parent.id,
                    "semantic_policy": SEMANTIC_POLICY_VERSION,
                    "development_disclaimer": True,
                },
            )
            regions.append(region)
            claims.append(
                SemanticClaim(
                    claim_type=claim_type,
                    region_id=region_id,
                    confidence=semantic_confidence,
                    metrics=region.metrics,
                    metadata=region.metadata,
                )
            )

        return SemanticAnalysisOutput(
            regions=regions,
            claims=claims,
            analyzer=self.name,
            mode=DataMode.DEVELOPMENT,
            analyzer_metadata={
                "semantic_policy": SEMANTIC_POLICY_VERSION,
                "analysis_profile": payload.analysis_profile,
                "message": "Development semantic adapter — not production evidence.",
            },
        )
