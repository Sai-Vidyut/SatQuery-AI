from __future__ import annotations

import math
from typing import Any

from app.adapters.change.earth_engine.sar_constants import (
    ANALYSIS_SCALE_M,
    DETECTOR_NAME,
    DETECTOR_VERSION,
    MAX_CHANGE_REGIONS,
    MIN_CONNECTED_PIXELS,
    MIN_REGION_AREA_M2,
    PROVENANCE_CHAIN,
    SAR_CHANGE_THRESHOLD_DB,
    SAR_CONFIDENCE_PERCENTILE,
    VECTORIZATION_SCALE_M,
)
from app.adapters.change.earth_engine.sar_metrics import compute_sar_confidence
from app.adapters.change.earth_engine.vectors import _polygon_area_m2_approx
from app.core.errors import SatQueryError
from app.schemas.domain import EvidenceRegion, GeoJSONGeometry, Metric


def _extract_mean_magnitude(properties: dict[str, Any]) -> float:
    for key in (
        "mean",
        "sar_change_magnitude_mean",
        "sar_change_magnitude",
        "change_magnitude_mean",
    ):
        if key in properties and properties[key] is not None:
            return float(properties[key])
    return 0.0


def _extract_max_magnitude(properties: dict[str, Any], mean: float) -> float:
    for key in ("max", "sar_change_magnitude_max", "change_magnitude_max"):
        if key in properties and properties[key] is not None:
            return float(properties[key])
    return mean


def _extract_percentile_magnitude(properties: dict[str, Any], mean: float) -> float:
    for key in (
        f"p{SAR_CONFIDENCE_PERCENTILE}",
        f"sar_change_magnitude_p{SAR_CONFIDENCE_PERCENTILE}",
        "sar_change_magnitude_p90",
        "percentile",
        "p90",
    ):
        if key in properties and properties[key] is not None:
            return float(properties[key])
    return mean


def vectorize_sar_change_regions(
    ee: Any,
    change_magnitude: Any,
    aoi_geometry: Any,
    threshold: float = SAR_CHANGE_THRESHOLD_DB,
    scale: float = ANALYSIS_SCALE_M,
    vector_scale: float = VECTORIZATION_SCALE_M,
) -> list[dict[str, Any]]:
    """
    Threshold SAR change magnitude, vectorize, and compute mean/max/p90 per region.
    """
    try:
        binary_mask = change_magnitude.gt(threshold).byte().rename("change_mask")
        connected = binary_mask.connectedPixelCount(maxSize=256, eightConnected=False)
        filtered_binary = binary_mask.updateMask(connected.gte(MIN_CONNECTED_PIXELS))

        pixel_count = (
            filtered_binary.reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=aoi_geometry,
                scale=vector_scale,
                maxPixels=1e9,
                bestEffort=True,
                tileScale=4,
            )
            .getInfo()
            .get("change_mask", 0)
        )
        if not pixel_count:
            return []

        vectors = filtered_binary.selfMask().reduceToVectors(
            geometry=aoi_geometry,
            scale=vector_scale,
            geometryType="polygon",
            eightConnected=False,
            maxPixels=1e9,
            bestEffort=True,
            tileScale=4,
        )
        vectors_clipped = ee.FeatureCollection(vectors).map(
            lambda f: ee.Feature(f.geometry().intersection(aoi_geometry, 1), f.toDictionary())
        )
        vectors_limited = vectors_clipped.limit(MAX_CHANGE_REGIONS * 4)
        stats = change_magnitude.reduceRegions(
            collection=vectors_limited,
            reducer=ee.Reducer.mean()
            .combine(reducer2=ee.Reducer.max(), sharedInputs=True)
            .combine(
                reducer2=ee.Reducer.percentile([SAR_CONFIDENCE_PERCENTILE]),
                sharedInputs=True,
            ),
            scale=vector_scale,
            tileScale=4,
        )
        result = stats.getInfo()
    except Exception as exc:
        raise SatQueryError(
            "earth_engine_request_failed",
            f"SAR change vectorization failed: {exc}",
            status_code=502,
        ) from exc

    if not result:
        return []
    return result.get("features", [])


def features_to_sar_evidence_regions(
    features: list[dict[str, Any]],
    *,
    polarization: str,
    before_scene_id: str,
    after_scene_id: str,
) -> list[EvidenceRegion]:
    """Convert EE vector features to SAR EvidenceRegion contracts."""
    parsed: list[tuple[float, EvidenceRegion]] = []

    for idx, feature in enumerate(features):
        geom = feature.get("geometry")
        if not geom:
            continue
        if geom.get("type") == "MultiPolygon":
            polys = geom.get("coordinates", [])
            if not polys:
                continue
            geom = {
                "type": "Polygon",
                "coordinates": max(polys, key=lambda p: _polygon_area_m2_approx(p[0])),
            }
        if geom.get("type") != "Polygon":
            continue

        coords = geom.get("coordinates")
        if not coords:
            continue

        area_m2 = _polygon_area_m2_approx(coords[0])
        if area_m2 < MIN_REGION_AREA_M2:
            continue

        props = feature.get("properties", {})
        mean_mag = _extract_mean_magnitude(props)
        max_mag = _extract_max_magnitude(props, mean_mag)
        p90_mag = _extract_percentile_magnitude(props, mean_mag)
        confidence = compute_sar_confidence(
            p90_mag,
            mean_value=mean_mag,
            max_value=max_mag,
        )
        area_km2 = round(area_m2 / 1_000_000.0, 6)

        region = EvidenceRegion(
            id=f"sar-change-region-{idx + 1:02d}",
            geometry=GeoJSONGeometry(type="Polygon", coordinates=coords),
            type="sar_change",
            confidence=confidence,
            metrics=[
                Metric(
                    name="area_km2",
                    value=area_km2,
                    unit="km²",
                    source=DETECTOR_NAME,
                ),
                Metric(
                    name="mean_sar_change_magnitude",
                    value=round(mean_mag, 3),
                    unit="db",
                    source=DETECTOR_NAME,
                ),
                Metric(
                    name="max_sar_change_magnitude",
                    value=round(max_mag, 3),
                    unit="db",
                    source=DETECTOR_NAME,
                ),
                Metric(
                    name="p90_sar_change_magnitude",
                    value=round(p90_mag, 3),
                    unit="db",
                    source=DETECTOR_NAME,
                ),
                Metric(
                    name="sar_change_threshold",
                    value=SAR_CHANGE_THRESHOLD_DB,
                    unit="db",
                    source=DETECTOR_NAME,
                ),
                Metric(
                    name="polarization",
                    value=polarization,
                    unit=None,
                    source=DETECTOR_NAME,
                ),
            ],
            source=DETECTOR_NAME,
            metadata={
                "detector_version": DETECTOR_VERSION,
                "claim_type": "none",
                "evidence_modality": "sar",
                "provenance_chain": list(PROVENANCE_CHAIN),
                "before_scene_id": before_scene_id,
                "after_scene_id": after_scene_id,
                "polarization": polarization,
                "confidence_percentile": SAR_CONFIDENCE_PERCENTILE,
                "vector_label": props.get("label"),
            },
        )
        parsed.append((area_m2, region))

    parsed.sort(key=lambda item: item[0], reverse=True)
    limited = parsed[:MAX_CHANGE_REGIONS]

    regions: list[EvidenceRegion] = []
    for rank, (_, region) in enumerate(limited, start=1):
        regions.append(region.model_copy(update={"id": f"sar-change-region-{rank:02d}"}))
    return regions
