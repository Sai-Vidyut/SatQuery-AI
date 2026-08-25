from __future__ import annotations

import asyncio
from typing import Any

from app.adapters.change.base import ChangeDetector
from app.adapters.change.earth_engine.sar import (
    compute_sar_change_magnitude,
    load_sar_scene_image,
    polarization_summary,
    prepare_sar_scene,
    primary_polarization_used,
)
from app.adapters.change.earth_engine.sar_constants import (
    ANALYSIS_SCALE_M,
    DETECTOR_NAME,
    DETECTOR_VERSION,
    SAR_CHANGE_THRESHOLD_DB,
    SAR_COLLECTION,
    SAR_POLARIZATIONS,
)
from app.adapters.change.earth_engine.sar_vectors import (
    features_to_sar_evidence_regions,
    vectorize_sar_change_regions,
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


def run_sar_change_detection(
    ee: Any,
    before_platform_id: str,
    after_platform_id: str,
    aoi_geometry: Any,
    threshold: float = SAR_CHANGE_THRESHOLD_DB,
    scale: float = ANALYSIS_SCALE_M,
) -> tuple[list[dict[str, Any]], str, dict[str, bool]]:
    """Orchestrate SAR change detection and return raw EE features (test seam)."""
    before = prepare_sar_scene(load_sar_scene_image(ee, before_platform_id), ee)
    after = prepare_sar_scene(load_sar_scene_image(ee, after_platform_id), ee)
    pol_summary = polarization_summary(before, after)
    polarization = primary_polarization_used(before, after)
    magnitude = compute_sar_change_magnitude(before, after, ee)
    features = vectorize_sar_change_regions(
        ee,
        magnitude,
        aoi_geometry,
        threshold=threshold,
        scale=scale,
    )
    return features, polarization, pol_summary


class EarthEngineSARChangeDetector(ChangeDetector):
    """
    Deterministic Sentinel-1 SAR change detection via Earth Engine backscatter differencing.
    Produces radar change evidence only — no semantic flood/construction/damage claims.
    """

    def __init__(self, client: EarthEngineClient | None = None) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return DETECTOR_NAME

    def _get_client(self) -> EarthEngineClient:
        if self._client is None:
            self._client = EarthEngineClient.initialize()
        return self._client

    async def detect(self, payload: ChangeDetectionInput) -> ChangeDetectionOutput:
        if payload.imagery.mode != DataMode.EARTH_ENGINE:
            raise SatQueryError(
                "change_detector_misconfigured",
                "Earth Engine SAR change detector requires imagery.mode=earth_engine.",
                status_code=400,
            )
        if payload.imagery.sensor != SensorType.SENTINEL_1:
            raise SatQueryError(
                "change_detector_misconfigured",
                "Earth Engine SAR change detector requires imagery.sensor=sentinel-1.",
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
            features, polarization, pol_summary = run_sar_change_detection(
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
                f"SAR change detection failed: {exc}",
                status_code=502,
            ) from exc

        regions = features_to_sar_evidence_regions(
            features,
            polarization=polarization,
            before_scene_id=before_scene.scene_id,
            after_scene_id=after_scene.scene_id,
        )

        return ChangeDetectionOutput(
            regions=regions,
            raw_detection_count=len(regions),
            detector=self.name,
            mode=DataMode.EARTH_ENGINE,
            detector_metadata={
                "detector_version": DETECTOR_VERSION,
                "method": "sar_backscatter_change",
                "collection": SAR_COLLECTION,
                "polarizations": list(SAR_POLARIZATIONS),
                "polarization_availability": pol_summary,
                "primary_polarization": polarization,
                "threshold_db": SAR_CHANGE_THRESHOLD_DB,
                "scale_m": ANALYSIS_SCALE_M,
                "before_scene_id": before_scene.scene_id,
                "after_scene_id": after_scene.scene_id,
                "vector_feature_count": len(features),
                "project": client.project,
                "sensor": SensorType.SENTINEL_1.value,
            },
        )

    @staticmethod
    def _validate_imagery(imagery: ImageryResult) -> None:
        if len(imagery.scenes) < 2:
            raise SatQueryError(
                "insufficient_imagery",
                "SAR change detection requires at least two Sentinel-1 scenes from the imagery pipeline.",
                status_code=400,
                field="imagery.scenes",
            )
        for scene in imagery.scenes[:2]:
            if not scene.platform_id:
                raise SatQueryError(
                    "invalid_imagery_metadata",
                    f"Scene '{scene.scene_id}' is missing platform_id required for Earth Engine SAR analysis.",
                    status_code=400,
                    field="imagery.scenes",
                )
