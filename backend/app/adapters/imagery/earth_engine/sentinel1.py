from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from app.adapters.imagery.earth_engine.constants import (
    SENTINEL1_GRD_COLLECTION,
    SENTINEL1_INSTRUMENT_MODE,
    SENTINEL1_POLARIZATIONS,
)
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.core.errors import SatQueryError


def _ms_to_date(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()


def _extract_s1_scene(image: Any, collection_id: str) -> SceneCandidate:
    props = image.getInfo().get("properties", {})
    system_index = props.get("system:index") or props.get("PRODUCT_ID") or image.id()
    time_start = props.get("system:time_start")
    if time_start is None:
        raise SatQueryError(
            "earth_engine_request_failed",
            "Sentinel-1 scene missing system:time_start property.",
            status_code=502,
        )

    polarizations = props.get("transmitterReceiverPolarisation") or []
    if isinstance(polarizations, str):
        polarizations = [polarizations]

    platform_id = f"{collection_id}/{system_index}"
    relative_orbit = props.get("relativeOrbitNumber_start") or props.get("relativeOrbitNumber")
    metadata = {
        "collection": collection_id,
        "system_index": system_index,
        "relative_orbit": relative_orbit,
        "orbit_direction": props.get("orbitProperties_pass"),
        "instrument_mode": props.get("instrumentMode"),
        "polarizations": list(polarizations),
        "resolution_m": props.get("resolution_m"),
    }

    return SceneCandidate(
        scene_id=str(system_index),
        platform_id=platform_id,
        acquisition_date=_ms_to_date(int(time_start)),
        cloud_cover_percent=0.0,
        metadata=metadata,
    )


def query_sentinel1_scenes(
    client: Any,
    ee: Any,
    aoi_geometry: Any,
    start_date: date,
    end_date: date,
    collection_id: str = SENTINEL1_GRD_COLLECTION,
) -> list[SceneCandidate]:
    """
    Query Sentinel-1 GRD scenes intersecting AOI within date range.
    Filters to IW mode with VV and VH polarizations available.
    """
    try:
        collection = client.image_collection(collection_id)
        filtered = (
            collection.filterBounds(aoi_geometry)
            .filterDate(start_date.isoformat(), end_date.isoformat())
            .filter(ee.Filter.eq("instrumentMode", SENTINEL1_INSTRUMENT_MODE))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        )
        count = filtered.size().getInfo()
    except Exception as exc:
        raise SatQueryError(
            "earth_engine_request_failed",
            f"Earth Engine Sentinel-1 query failed: {exc}",
            status_code=502,
        ) from exc

    if count == 0:
        raise SatQueryError(
            "no_imagery_found",
            "No Sentinel-1 GRD scenes found for AOI and date range. "
            "Try widening the date range.",
            status_code=404,
        )

    try:
        image_list = filtered.toList(count)
        candidates: list[SceneCandidate] = []
        for i in range(count):
            image = ee.Image(image_list.get(i))
            candidates.append(_extract_s1_scene(image, collection_id))
        return candidates
    except SatQueryError:
        raise
    except Exception as exc:
        raise SatQueryError(
            "earth_engine_request_failed",
            f"Failed to read Sentinel-1 scene metadata: {exc}",
            status_code=502,
        ) from exc


def _sort_key_distance_to(target: date, scene: SceneCandidate) -> tuple:
    distance = abs((scene.acquisition_date - target).days)
    return (distance, scene.scene_id)


def select_s1_anchor_scenes(
    candidates: list[SceneCandidate],
    start_date: date,
    end_date: date,
) -> list[SceneCandidate]:
    """
    Deterministic Sentinel-1 anchor selection (policy v1.0.0).
    Requires scenes from a single relative orbit for meaningful SAR comparison.
    """
    if not candidates:
        raise SatQueryError(
            "no_imagery_found",
            "No Sentinel-1 scenes available for anchor selection.",
            status_code=404,
        )

    midpoint = start_date + (end_date - start_date) / 2
    by_orbit: dict[int, list[SceneCandidate]] = defaultdict(list)
    for scene in candidates:
        orbit = scene.metadata.get("relative_orbit")
        if orbit is None:
            continue
        by_orbit[int(orbit)].append(scene)

    if not by_orbit:
        raise SatQueryError(
            "no_imagery_found",
            "Sentinel-1 scenes are missing relativeOrbitNumber metadata.",
            status_code=404,
        )

    def orbit_score(orbit_scenes: list[SceneCandidate]) -> tuple:
        before = sum(1 for s in orbit_scenes if s.acquisition_date <= midpoint)
        after = sum(1 for s in orbit_scenes if s.acquisition_date > midpoint)
        has_both = 1 if before > 0 and after > 0 else 0
        return (has_both, len(orbit_scenes), -min(s.metadata.get("relative_orbit", 0) for s in orbit_scenes))

    best_orbit = max(by_orbit.items(), key=lambda item: orbit_score(item[1]))[0]
    orbit_candidates = by_orbit[best_orbit]

    start_scene = min(orbit_candidates, key=lambda s: _sort_key_distance_to(start_date, s))
    end_scene = min(orbit_candidates, key=lambda s: _sort_key_distance_to(end_date, s))

    selected: dict[str, SceneCandidate] = {
        start_scene.scene_id: start_scene,
        end_scene.scene_id: end_scene,
    }
    return sorted(selected.values(), key=lambda s: s.acquisition_date)


def scene_has_polarizations(scene: SceneCandidate, polarizations: tuple[str, ...] = SENTINEL1_POLARIZATIONS) -> dict[str, bool]:
    """Report VV/VH availability from scene metadata."""
    available = set(scene.metadata.get("polarizations") or [])
    return {pol: pol in available for pol in polarizations}
