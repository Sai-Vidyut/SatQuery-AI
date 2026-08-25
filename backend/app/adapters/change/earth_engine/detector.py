from __future__ import annotations

import asyncio
from typing import Any

from app.adapters.change.base import ChangeDetector
from app.adapters.change.earth_engine.constants import (
    ANALYSIS_SCALE_M,
    CVA_BANDS,
    CVA_MAGNITUDE_THRESHOLD,
    DETECTOR_VERSION,
)
from app.adapters.change.earth_engine.cva import (
    compute_change_magnitude,
    load_scene_image,
    prepare_scene,
)
from app.adapters.change.earth_engine.vectors import (
    features_to_evidence_regions,
    vectorize_change_regions,
)
from app.adapters.imagery.earth_engine.client import EarthEngineClient
from app.adapters.imagery.earth_engine.geometry import geojson_to_ee_geometry
from app.core.errors import SatQueryError
from app.schemas.domain import (
    ChangeDetectionInput,
    ChangeDetectionOutput,
    DataMode,
    ImageryResult,
    SensorType,
)


def run_cva_detection(
    ee: Any,
    before_platform_id: str,
    after_platform_id: str,
    aoi_geometry: Any,
    threshold: float = CVA_MAGNITUDE_THRESHOLD,
    scale: float = ANALYSIS_SCALE_M,
) -> list[dict[str, Any]]:
    """Orchestrate CVA and return raw EE vector features (test seam)."""
    before = prepare_scene(load_scene_image(ee, before_platform_id), ee)
    after = prepare_scene(load_scene_image(ee, after_platform_id), ee)
    magnitude = compute_change_magnitude(before, after, ee)
    return vectorize_change_regions(ee, magnitude, aoi_geometry, threshold=threshold, scale=scale)


class EarthEngineChangeDetector(ChangeDetector):
    """
    Deterministic Sentinel-2 change detection via Earth Engine Change Vector Analysis.
    All EE-specific logic stays in app.adapters.change.earth_engine.*.
    """

    def __init__(self, client: EarthEngineClient | None = None) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return "earth_engine_cva"

    def _get_client(self) -> EarthEngineClient:
        if self._client is None:
            self._client = EarthEngineClient.initialize()
        return self._client

    async def detect(self, payload: ChangeDetectionInput) -> ChangeDetectionOutput:
        if payload.imagery.mode != DataMode.EARTH_ENGINE:
            raise SatQueryError(
                "change_detector_misconfigured",
                "Earth Engine change detector requires imagery.mode=earth_engine. "
                "Use DeterministicChangeDetector for development imagery.",
                status_code=400,
            )
        if payload.imagery.sensor != SensorType.SENTINEL_2:
            raise SatQueryError(
                "change_detector_misconfigured",
                "Earth Engine CVA change detector requires imagery.sensor=sentinel-2. "
                "Use the SAR change detector for Sentinel-1 imagery.",
                status_code=400,
            )
        self._validate_imagery(payload.imagery)
        return await asyncio.to_thread(self._detect_sync, payload)

    def _detect_sync(self, payload: ChangeDetectionInput) -> ChangeDetectionOutput:
        client = self._get_client()
        ee = client.ee
        aoi_geom = geojson_to_ee_geometry(ee, payload.aoi.geometry)

        before_scene = payload.imagery.scenes[0]
        after_scene = payload.imagery.scenes[-1]
        assert before_scene.platform_id and after_scene.platform_id

        try:
            features = run_cva_detection(
                ee,
                before_scene.platform_id,
                after_scene.platform_id,
                aoi_geom,
            )
        except SatQueryError:
            raise
        except Exception as exc:
            raise SatQueryError(
                "earth_engine_request_failed",
                f"Change detection failed: {exc}",
                status_code=502,
            ) from exc

        regions = features_to_evidence_regions(features)

        return ChangeDetectionOutput(
            regions=regions,
            raw_detection_count=len(regions),
            detector=self.name,
            mode=DataMode.EARTH_ENGINE,
            detector_metadata={
                "detector_version": DETECTOR_VERSION,
                "method": "change_vector_analysis",
                "bands": CVA_BANDS,
                "threshold": CVA_MAGNITUDE_THRESHOLD,
                "scale_m": ANALYSIS_SCALE_M,
                "before_scene_id": before_scene.scene_id,
                "after_scene_id": after_scene.scene_id,
                "vector_feature_count": len(features),
                "project": client.project,
            },
        )

    @staticmethod
    def _validate_imagery(imagery: ImageryResult) -> None:
        if len(imagery.scenes) < 2:
            raise SatQueryError(
                "insufficient_imagery",
                "Change detection requires at least two Sentinel-2 scenes from the imagery pipeline.",
                status_code=400,
                field="imagery.scenes",
            )
        for scene in imagery.scenes[:2]:
            if not scene.platform_id:
                raise SatQueryError(
                    "invalid_imagery_metadata",
                    f"Scene '{scene.scene_id}' is missing platform_id required for Earth Engine analysis.",
                    status_code=400,
                    field="imagery.scenes",
                )
