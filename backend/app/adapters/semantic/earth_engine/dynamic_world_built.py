from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from app.adapters.imagery.earth_engine.client import EarthEngineClient
from app.adapters.imagery.earth_engine.geometry import geojson_to_ee_geometry
from app.adapters.semantic.base import SemanticAnalyzer
from app.adapters.semantic.earth_engine.constants import (
    ANALYSIS_SCALE_M,
    ANALYZER_NAME,
    BUILT_BAND,
    DYNAMIC_WORLD_COLLECTION,
    POLICY_NAME,
    POLICY_VERSION,
    PROVENANCE_CHAIN,
    TEMPORAL_WINDOW_POLICY,
)
from app.adapters.semantic.earth_engine.metrics import (
    compute_delta_built,
    compute_semantic_confidence,
    passes_semantic_thresholds,
    polygon_area_m2,
)
from app.adapters.semantic.earth_engine.imagery_epoch import imagery_epoch_window
from app.core.errors import SatQueryError
from app.evidence.fusion import compute_overlap_fraction
from app.schemas.domain import (
    DataMode,
    EvidenceRegion,
    GeoJSONGeometry,
    ImageryResult,
    ImageryScene,
    Metric,
    SemanticAnalysisInput,
    SemanticAnalysisOutput,
    SemanticClaim,
)

SUPPORTED_CLAIMS = ["construction_candidate"]


def sample_built_probability(
    ee: Any,
    client: EarthEngineClient,
    geometry: Any,
    window_start: date,
    window_end: date,
    scale: float = ANALYSIS_SCALE_M,
) -> float:
    """Sample mean Dynamic World built probability over geometry and date window."""
    collection = client.image_collection(DYNAMIC_WORLD_COLLECTION)
    filtered = (
        collection.filterBounds(geometry)
        .filterDate(window_start.isoformat(), window_end.isoformat())
    )
    count = filtered.size().getInfo()
    if count == 0:
        return 0.0

    built_mean_image = filtered.select(BUILT_BAND).mean()
    stats = built_mean_image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=scale,
        maxPixels=1e9,
        bestEffort=True,
        tileScale=4,
    ).getInfo()
    value = stats.get(BUILT_BAND)
    return float(value) if value is not None else 0.0


def evaluate_cva_region(
    ee: Any,
    client: EarthEngineClient,
    cva_region: EvidenceRegion,
    earlier_scene: ImageryScene,
    later_scene: ImageryScene,
) -> dict[str, Any] | None:
    """Evaluate one CVA region; return candidate dict or None if thresholds fail."""
    ring = cva_region.geometry.coordinates[0]
    area_m2 = polygon_area_m2(ring)
    ee_geometry = geojson_to_ee_geometry(ee, cva_region.geometry)

    earlier_start, earlier_end = imagery_epoch_window(earlier_scene)
    later_start, later_end = imagery_epoch_window(later_scene)

    earlier_mean = sample_built_probability(ee, client, ee_geometry, earlier_start, earlier_end)
    later_mean = sample_built_probability(ee, client, ee_geometry, later_start, later_end)
    delta_built = compute_delta_built(earlier_mean, later_mean)

    semantic_region = EvidenceRegion(
        id=f"semantic-eval-{cva_region.id}",
        geometry=cva_region.geometry,
        type="semantic_evidence",
        confidence=compute_semantic_confidence(delta_built),
        metrics=[],
        source=ANALYZER_NAME,
        metadata={"parent_region_id": cva_region.id},
    )
    overlap_fraction = compute_overlap_fraction(cva_region, semantic_region)

    if not passes_semantic_thresholds(delta_built, overlap_fraction, area_m2):
        return None

    return {
        "cva_region": cva_region,
        "earlier_built_mean": round(earlier_mean, 4),
        "later_built_mean": round(later_mean, 4),
        "delta_built": delta_built,
        "overlap_fraction": overlap_fraction,
        "area_m2": area_m2,
        "area_km2": round(area_m2 / 1_000_000.0, 6),
        "confidence": compute_semantic_confidence(delta_built),
        "earlier_window": (earlier_start.isoformat(), earlier_end.isoformat()),
        "later_window": (later_start.isoformat(), later_end.isoformat()),
    }


class EarthEngineDynamicWorldBuiltAnalyzer(SemanticAnalyzer):
    """
    Dynamic World built-probability temporal comparison for construction candidates.
    All EE logic stays in app.adapters.semantic.earth_engine.*.
    """

    def __init__(self, client: EarthEngineClient | None = None) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return ANALYZER_NAME

    @property
    def supported_claims(self) -> list[str]:
        return list(SUPPORTED_CLAIMS)

    def _get_client(self) -> EarthEngineClient:
        if self._client is None:
            self._client = EarthEngineClient.initialize()
        return self._client

    async def analyze(self, payload: SemanticAnalysisInput) -> SemanticAnalysisOutput:
        if payload.imagery.mode != DataMode.EARTH_ENGINE:
            raise SatQueryError(
                "semantic_analyzer_misconfigured",
                "Earth Engine semantic analyzer requires imagery.mode=earth_engine.",
                status_code=400,
            )
        self._validate_imagery(payload.imagery)
        return await asyncio.to_thread(self._analyze_sync, payload)

    def _analyze_sync(self, payload: SemanticAnalysisInput) -> SemanticAnalysisOutput:
        client = self._get_client()
        ee = client.ee

        earlier_scene = payload.imagery.scenes[0]
        later_scene = payload.imagery.scenes[-1]

        regions: list[EvidenceRegion] = []
        claims: list[SemanticClaim] = []
        evaluated = 0

        try:
            for idx, cva_region in enumerate(payload.change_regions, start=1):
                evaluated += 1
                result = evaluate_cva_region(ee, client, cva_region, earlier_scene, later_scene)
                if result is None:
                    continue

                region_id = f"semantic-candidate-{idx:02d}"
                region = EvidenceRegion(
                    id=region_id,
                    geometry=GeoJSONGeometry(
                        type="Polygon",
                        coordinates=cva_region.geometry.coordinates,
                    ),
                    type="semantic_evidence",
                    confidence=result["confidence"],
                    metrics=[
                        Metric(
                            name="delta_built_probability",
                            value=result["delta_built"],
                            unit="probability",
                            source=ANALYZER_NAME,
                        ),
                        Metric(
                            name="earlier_built_mean",
                            value=result["earlier_built_mean"],
                            unit="probability",
                            source=ANALYZER_NAME,
                        ),
                        Metric(
                            name="later_built_mean",
                            value=result["later_built_mean"],
                            unit="probability",
                            source=ANALYZER_NAME,
                        ),
                        Metric(
                            name="overlap_fraction",
                            value=result["overlap_fraction"],
                            unit="ratio",
                            source=ANALYZER_NAME,
                        ),
                        Metric(
                            name="area_km2",
                            value=result["area_km2"],
                            unit="km²",
                            source=ANALYZER_NAME,
                        ),
                    ],
                    source=ANALYZER_NAME,
                    metadata={
                        "claim_type": "construction_candidate",
                        "provenance_chain": list(PROVENANCE_CHAIN),
                        "parent_region_id": cva_region.id,
                        "semantic_policy": POLICY_NAME,
                        "policy_version": POLICY_VERSION,
                        "dataset": DYNAMIC_WORLD_COLLECTION,
                        "band": BUILT_BAND,
                        "earlier_anchor_date": earlier_scene.acquisition_date.isoformat(),
                        "later_anchor_date": later_scene.acquisition_date.isoformat(),
                        "earlier_window": result["earlier_window"],
                        "later_window": result["later_window"],
                    },
                )
                regions.append(region)
                claims.append(
                    SemanticClaim(
                        claim_type="construction_candidate",
                        region_id=region_id,
                        confidence=result["confidence"],
                        metrics=region.metrics,
                        metadata=region.metadata,
                    )
                )
        except SatQueryError:
            raise
        except Exception as exc:
            raise SatQueryError(
                "earth_engine_request_failed",
                f"Dynamic World semantic analysis failed: {exc}",
                status_code=502,
            ) from exc

        return SemanticAnalysisOutput(
            regions=regions,
            claims=claims,
            analyzer=self.name,
            mode=DataMode.EARTH_ENGINE,
            analyzer_metadata={
                "policy": POLICY_NAME,
                "version": POLICY_VERSION,
                "dataset": DYNAMIC_WORLD_COLLECTION,
                "band": BUILT_BAND,
                "temporal_window_policy": TEMPORAL_WINDOW_POLICY,
                "earlier_anchor_date": earlier_scene.acquisition_date.isoformat(),
                "later_anchor_date": later_scene.acquisition_date.isoformat(),
                "cva_regions_evaluated": evaluated,
                "semantic_candidates": len(regions),
                "project": client.project,
            },
        )

    @staticmethod
    def _validate_imagery(imagery: ImageryResult) -> None:
        if len(imagery.scenes) < 2:
            raise SatQueryError(
                "insufficient_imagery",
                "Semantic analysis requires at least two imagery scenes with acquisition dates.",
                status_code=400,
                field="imagery.scenes",
            )
