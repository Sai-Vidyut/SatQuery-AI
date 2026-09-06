from __future__ import annotations

import asyncio
from typing import Any

from app.adapters.change.base import ChangeDetector
from app.adapters.change.earth_engine.constants import (
    ANALYSIS_SCALE_M,
    CVA_BANDS,
    CVA_MAGNITUDE_THRESHOLD,
    DETECTOR_VERSION,
    INDEX_CHANGE_THRESHOLDS,
)
from app.adapters.change.earth_engine.cva import (
    compute_change_magnitude,
    load_scene_image,
    prepare_scene,
)
from app.adapters.change.earth_engine.indices import (
    classify_direction_hint_from_median,
    compute_index_change_magnitude,
    select_primary_index_for_catalog,
)
from app.adapters.change.earth_engine.vectors import (
    features_to_evidence_regions,
    vectorize_change_regions,
)
from app.adapters.imagery.earth_engine.client import EarthEngineClient
from app.adapters.imagery.earth_engine.geometry import geojson_to_ee_geometry
from app.core.errors import SatQueryError
from app.schemas.change_domain import ChangeDomain
from app.schemas.domain import (
    ChangeDetectionInput,
    ChangeDetectionOutput,
    DataMode,
    ImageryResult,
    SensorType,
)


def _resolve_change_domain(value: str | None) -> ChangeDomain | None:
    if not value:
        return None
    try:
        return ChangeDomain(value)
    except ValueError:
        return None


def _index_threshold(index_name: str) -> float:
    return INDEX_CHANGE_THRESHOLDS.get(index_name.lower(), CVA_MAGNITUDE_THRESHOLD)


def _confidence_reference(threshold: float) -> float:
    return threshold * 3.0


def run_cva_detection(
    ee: Any,
    before_platform_id: str,
    after_platform_id: str,
    aoi_geometry: Any,
    threshold: float = CVA_MAGNITUDE_THRESHOLD,
    scale: float = ANALYSIS_SCALE_M,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Orchestrate CVA and return raw EE vector features plus detection context."""
    before = prepare_scene(load_scene_image(ee, before_platform_id), ee)
    after = prepare_scene(load_scene_image(ee, after_platform_id), ee)
    magnitude = compute_change_magnitude(before, after, ee)
    features = vectorize_change_regions(ee, magnitude, aoi_geometry, threshold=threshold, scale=scale)
    return features, {"method": "change_vector_analysis", "threshold": threshold, "primary_index": None}


def run_index_detection(
    ee: Any,
    before_platform_id: str,
    after_platform_id: str,
    aoi_geometry: Any,
    primary_index: str,
    scale: float = ANALYSIS_SCALE_M,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Domain-aware index differencing on masked Sentinel-2 SR scenes."""
    before = prepare_scene(load_scene_image(ee, before_platform_id), ee)
    after = prepare_scene(load_scene_image(ee, after_platform_id), ee)
    threshold = _index_threshold(primary_index)
    magnitude, signed = compute_index_change_magnitude(before, after, primary_index, ee)
    features = vectorize_change_regions(ee, magnitude, aoi_geometry, threshold=threshold, scale=scale)

    direction_hint = "no_change"
    if features:
        try:
            changed_mask = magnitude.gt(threshold)
            masked_signed = signed.updateMask(changed_mask)
            stats = (
                masked_signed.reduceRegion(
                    reducer=ee.Reducer.median(),
                    geometry=aoi_geometry,
                    scale=scale,
                    maxPixels=1e9,
                    bestEffort=True,
                    tileScale=4,
                )
                .getInfo()
            )
            median_delta = float(stats.get("signed_index_diff", 0) or 0)
            direction_hint = classify_direction_hint_from_median(median_delta, primary_index)
        except Exception:
            direction_hint = "no_change"

    return features, {
        "method": "index_differencing",
        "threshold": threshold,
        "primary_index": primary_index,
        "change_direction_hint": direction_hint,
        "normalization": "none",
    }


class EarthEngineChangeDetector(ChangeDetector):
    """
    Deterministic Sentinel-2 change detection via Earth Engine.

    Generic queries: Change Vector Analysis (unchanged from v1.1.0).
    Domain-aware catalog queries: primary index differencing (NDVI/NDWI/NDBI).
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

        domain = _resolve_change_domain(payload.change_domain)
        primary_index = select_primary_index_for_catalog(
            change_domain=domain,
            query_hint=payload.query_hint,
        )

        try:
            if primary_index:
                features, detection_ctx = run_index_detection(
                    ee,
                    before_scene.platform_id,
                    after_scene.platform_id,
                    aoi_geom,
                    primary_index,
                )
            else:
                features, detection_ctx = run_cva_detection(
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
        seasonality = (payload.imagery.provider_metadata or {}).get("seasonality", {})

        detector_metadata: dict[str, Any] = {
            "detector_version": DETECTOR_VERSION,
            "method": detection_ctx["method"],
            "bands": CVA_BANDS if detection_ctx["method"] == "change_vector_analysis" else None,
            "primary_index": detection_ctx.get("primary_index"),
            "threshold": detection_ctx["threshold"],
            "scale_m": ANALYSIS_SCALE_M,
            "before_scene_id": before_scene.scene_id,
            "after_scene_id": after_scene.scene_id,
            "before_acquisition_date": before_scene.acquisition_date.isoformat(),
            "after_acquisition_date": after_scene.acquisition_date.isoformat(),
            "requested_earlier_date": payload.earlier_date.isoformat(),
            "requested_later_date": payload.later_date.isoformat(),
            "vector_feature_count": len(features),
            "project": client.project,
            "change_domain": domain.value if domain else None,
            "seasonality": seasonality,
        }
        if detection_ctx.get("change_direction_hint"):
            detector_metadata["change_direction_hint"] = detection_ctx["change_direction_hint"]
        if detection_ctx.get("normalization"):
            detector_metadata["normalization"] = detection_ctx["normalization"]
        if seasonality.get("warnings"):
            detector_metadata["seasonality_warnings"] = seasonality["warnings"]

        return ChangeDetectionOutput(
            regions=regions,
            raw_detection_count=len(regions),
            detector=self.name,
            mode=DataMode.EARTH_ENGINE,
            detector_metadata=detector_metadata,
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
