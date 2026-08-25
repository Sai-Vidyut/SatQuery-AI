from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from app.adapters.imagery.earth_engine.constants import SENTINEL2_SR_COLLECTION
from app.core.errors import SatQueryError


@dataclass(frozen=True)
class SceneCandidate:
    """Normalized scene record from Earth Engine before selection."""

    scene_id: str
    platform_id: str
    acquisition_date: date
    cloud_cover_percent: float
    metadata: dict[str, Any]


def _ms_to_date(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()


def _extract_scene(image: Any, collection_id: str) -> SceneCandidate:
    props = image.getInfo().get("properties", {})
    system_index = props.get("system:index") or props.get("PRODUCT_ID") or image.id()
    time_start = props.get("system:time_start")
    if time_start is None:
        raise SatQueryError(
            "earth_engine_request_failed",
            "Scene missing system:time_start property.",
            status_code=502,
        )

    cloud = props.get("CLOUDY_PIXEL_PERCENTAGE")
    if cloud is None:
        cloud = props.get("CLOUD_COVER") or 0.0

    platform_id = f"{collection_id}/{system_index}"
    metadata = {
        "collection": collection_id,
        "system_index": system_index,
        "spacecraft": props.get("SPACECRAFT_NAME"),
        "mgrs_tile": props.get("MGRS_TILE"),
        "processing_level": props.get("PROCESSING_LEVEL"),
        "bands": [
            "B2", "B3", "B4", "B8", "B11", "B12",
        ],
    }

    return SceneCandidate(
        scene_id=str(system_index),
        platform_id=platform_id,
        acquisition_date=_ms_to_date(int(time_start)),
        cloud_cover_percent=float(cloud),
        metadata=metadata,
    )


def query_sentinel2_scenes(
    client: Any,
    ee: Any,
    aoi_geometry: Any,
    start_date: date,
    end_date: date,
    cloud_cover_max: float,
    collection_id: str = SENTINEL2_SR_COLLECTION,
) -> list[SceneCandidate]:
    """
    Query Sentinel-2 SR scenes intersecting AOI within date range.
    Raises SatQueryError on empty results or EE failures.
    """
    try:
        collection = client.image_collection(collection_id)
        filtered = (
            collection.filterBounds(aoi_geometry)
            .filterDate(start_date.isoformat(), end_date.isoformat())
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_cover_max))
        )
        count = filtered.size().getInfo()
    except Exception as exc:
        raise SatQueryError(
            "earth_engine_request_failed",
            f"Earth Engine query failed: {exc}",
            status_code=502,
        ) from exc

    if count == 0:
        raise SatQueryError(
            "no_imagery_found",
            "No Sentinel-2 scenes found for AOI and date range. "
            "Try widening the date range or increasing cloud_cover_max.",
            status_code=404,
        )

    try:
        image_list = filtered.toList(count)
        candidates: list[SceneCandidate] = []
        for i in range(count):
            image = ee.Image(image_list.get(i))
            candidates.append(_extract_scene(image, collection_id))
        return candidates
    except SatQueryError:
        raise
    except Exception as exc:
        raise SatQueryError(
            "earth_engine_request_failed",
            f"Failed to read Sentinel-2 scene metadata: {exc}",
            status_code=502,
        ) from exc
