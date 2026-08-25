from __future__ import annotations

import math
from typing import Any

from app.adapters.change.earth_engine.constants import (
    ANALYSIS_SCALE_M,
    CVA_CONFIDENCE_REFERENCE_MAGNITUDE,
    CVA_MAGNITUDE_THRESHOLD,
    DETECTOR_VERSION,
    MAX_CHANGE_REGIONS,
    MIN_CONNECTED_PIXELS,
    MIN_REGION_AREA_M2,
    VECTORIZATION_SCALE_M,
)
from app.core.errors import SatQueryError
from app.schemas.domain import EvidenceRegion, GeoJSONGeometry, Metric


def _polygon_area_m2_approx(coords: list[list[float]]) -> float:
    """Shoelace area on lon/lat ring with latitude correction (deterministic, no EE call)."""
    if len(coords) < 3:
        return 0.0
    ring = coords[:-1] if coords[0] == coords[-1] else coords
    if len(ring) < 3:
        return 0.0

    mean_lat = sum(p[1] for p in ring) / len(ring)
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * math.cos(math.radians(mean_lat))

    area = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i][0] * lon_scale, ring[i][1] * lat_scale
        x2, y2 = ring[(i + 1) % len(ring)][0] * lon_scale, ring[(i + 1) % len(ring)][1] * lat_scale
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _confidence_from_magnitude(mean_magnitude: float) -> float:
    if mean_magnitude <= CVA_MAGNITUDE_THRESHOLD:
        return 0.0
    span = CVA_CONFIDENCE_REFERENCE_MAGNITUDE - CVA_MAGNITUDE_THRESHOLD
    if span <= 0:
        return 1.0
    return round(min(1.0, (mean_magnitude - CVA_MAGNITUDE_THRESHOLD) / span), 3)


def _extract_mean_magnitude(properties: dict[str, Any]) -> float:
    for key in ("mean", "change_magnitude", "change_magnitude_mean"):
        if key in properties and properties[key] is not None:
            return float(properties[key])
    return 0.0


def _extract_max_magnitude(properties: dict[str, Any], mean: float) -> float:
    for key in ("max", "change_magnitude_max"):
        if key in properties and properties[key] is not None:
            return float(properties[key])
    return mean


def vectorize_change_regions(
    ee: Any,
    change_magnitude: Any,
    aoi_geometry: Any,
    threshold: float = CVA_MAGNITUDE_THRESHOLD,
    scale: float = ANALYSIS_SCALE_M,
    vector_scale: float = VECTORIZATION_SCALE_M,
) -> list[dict[str, Any]]:
    """
    Threshold change magnitude, vectorize connected components, return raw EE features.
    Uses a coarser vectorization scale and connected-pixel filtering to avoid EE limits.
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
        # Single-band image: compute mean/max per polygon via reduceRegions, not reduceToVectors.
        stats = change_magnitude.reduceRegions(
            collection=vectors_limited,
            reducer=ee.Reducer.mean().combine(
                reducer2=ee.Reducer.max(),
                sharedInputs=True,
            ),
            scale=scale,
            tileScale=4,
        )
        result = stats.getInfo()
    except Exception as exc:
        raise SatQueryError(
            "earth_engine_request_failed",
            f"Change vectorization failed: {exc}",
            status_code=502,
        ) from exc

    if not result:
        return []
    return result.get("features", [])


def features_to_evidence_regions(features: list[dict[str, Any]]) -> list[EvidenceRegion]:
    """Convert EE vector features to EvidenceRegion contracts with deterministic metrics."""
    parsed: list[tuple[float, EvidenceRegion]] = []

    for idx, feature in enumerate(features):
        geom = feature.get("geometry")
        if not geom:
            continue
        if geom.get("type") == "MultiPolygon":
            # Keep largest constituent polygon after AOI clip.
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
        confidence = _confidence_from_magnitude(mean_mag)
        area_km2 = round(area_m2 / 1_000_000.0, 6)

        region = EvidenceRegion(
            id=f"change-region-{idx + 1:02d}",
            geometry=GeoJSONGeometry(type="Polygon", coordinates=coords),
            type="spectral_change",
            confidence=confidence,
            metrics=[
                Metric(
                    name="area_km2",
                    value=area_km2,
                    unit="km²",
                    source="earth_engine_cva",
                ),
                Metric(
                    name="mean_change_magnitude",
                    value=round(mean_mag, 2),
                    unit="sr_euclidean",
                    source="earth_engine_cva",
                ),
                Metric(
                    name="max_change_magnitude",
                    value=round(max_mag, 2),
                    unit="sr_euclidean",
                    source="earth_engine_cva",
                ),
                Metric(
                    name="cva_threshold",
                    value=CVA_MAGNITUDE_THRESHOLD,
                    unit="sr_euclidean",
                    source="earth_engine_cva",
                ),
            ],
            source="earth_engine_cva",
            metadata={
                "detector_version": DETECTOR_VERSION,
                "vector_label": props.get("label"),
            },
        )
        parsed.append((area_m2, region))

    parsed.sort(key=lambda item: item[0], reverse=True)
    limited = parsed[:MAX_CHANGE_REGIONS]

    regions: list[EvidenceRegion] = []
    for rank, (_, region) in enumerate(limited, start=1):
        regions.append(region.model_copy(update={"id": f"change-region-{rank:02d}"}))
    return regions
