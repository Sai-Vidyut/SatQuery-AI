"""Deterministic mock ground-level context for selected bi-temporal change regions."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from app.core.errors import SatQueryError
from app.schemas.domain import AnalysisResult, EvidenceRegion
from app.schemas.ground_context import (
    GroundContextImage,
    GroundContextLocation,
    GroundContextProvenance,
    GroundContextResult,
    GroundContextScene,
    GroundSceneCategory,
)
from app.services.region_interpretation import _find_region
from app.services.session_store import SessionStore, session_store

_SCENE_DEFINITIONS: dict[GroundSceneCategory, dict[str, object]] = {
    "vegetation_loss": {
        "title": "Roadside vegetation context",
        "description": (
            "Demonstration ground-level context showing sparse vegetation, exposed soil, "
            "and nearby built surfaces."
        ),
        "features": [
            "sparse vegetation",
            "exposed soil",
            "roadside/open area",
            "nearby structures",
        ],
        "asset_id": "mock-ground-panorama-scenic",
        "url": "/mock-ground/panorama-scenic-overlook.jpg",
        "alt": "Demonstration scenic overlook panorama (not real Street View)",
    },
    "built_up_increase": {
        "title": "Developed roadside context",
        "description": (
            "Demonstration ground-level context showing dense built surfaces, "
            "construction-like activity, and nearby road access."
        ),
        "features": [
            "dense built surfaces",
            "construction-like area",
            "impervious ground",
            "nearby road access",
        ],
        "asset_id": "mock-ground-panorama-street",
        "url": "/mock-ground/panorama-roadside-street.jpg",
        "alt": "Demonstration streetscape panorama (not real Street View)",
    },
    "water_shrinkage": {
        "title": "Water-edge context",
        "description": (
            "Demonstration ground-level context showing an exposed shoreline, "
            "a wet/dry boundary, and adjacent access paths."
        ),
        "features": [
            "exposed shoreline",
            "wet/dry boundary",
            "sparse vegetation",
            "adjacent access path",
        ],
        "asset_id": "mock-ground-panorama-scenic",
        "url": "/mock-ground/panorama-scenic-overlook.jpg",
        "alt": "Demonstration river valley panorama (not real Street View)",
    },
    "flood": {
        "title": "Low-lying wet-area context",
        "description": (
            "Demonstration ground-level context showing waterlogged surfaces, "
            "access disruption, and surrounding structures."
        ),
        "features": [
            "waterlogged surfaces",
            "access disruption",
            "wet ground",
            "surrounding structures",
        ],
        "asset_id": "mock-ground-panorama-scenic",
        "url": "/mock-ground/panorama-scenic-overlook.jpg",
        "alt": "Demonstration low-lying wet-area panorama (not real Street View)",
    },
    "generic_change": {
        "title": "Open-area ground context",
        "description": (
            "Demonstration ground-level context showing mixed open surfaces, "
            "access paths, and nearby built features."
        ),
        "features": [
            "mixed open surfaces",
            "access path",
            "nearby structures",
            "contextual surroundings",
        ],
        "asset_id": "mock-ground-panorama-street",
        "url": "/mock-ground/panorama-roadside-street.jpg",
        "alt": "Demonstration open-area street panorama (not real Street View)",
    },
}

_DIRECTION_TO_CATEGORY: dict[str, GroundSceneCategory] = {
    "vegetation_loss": "vegetation_loss",
    "vegetation_gain": "vegetation_loss",
    "built_up_increase": "built_up_increase",
    "built_up_decrease": "built_up_increase",
    "water_contraction": "water_shrinkage",
    "water_expansion": "flood",
}


def polygon_centroid_wgs84(geometry: dict) -> tuple[float, float]:
    """Return (longitude, latitude) centroid for a GeoJSON Polygon ring in WGS84."""
    if geometry.get("type") != "Polygon":
        raise SatQueryError(
            "invalid_region_geometry",
            "Ground context requires a polygon geometry for the selected region.",
            status_code=422,
            field="geometry",
        )
    coordinates = geometry.get("coordinates")
    if not coordinates or not coordinates[0]:
        raise SatQueryError(
            "invalid_region_geometry",
            "Ground context requires polygon coordinates for the selected region.",
            status_code=422,
            field="geometry",
        )
    ring = coordinates[0]
    coords = ring[:-1] if ring and ring[0] == ring[-1] else ring
    if not coords:
        raise SatQueryError(
            "invalid_region_geometry",
            "Ground context could not derive a centroid for the selected region.",
            status_code=422,
            field="geometry",
        )
    lon = sum(point[0] for point in coords) / len(coords)
    lat = sum(point[1] for point in coords) / len(coords)
    return lon, lat


def _stable_digest(*parts: str) -> bytes:
    return hashlib.sha256("|".join(parts).encode()).digest()


def _stable_int(session_id: str, region_id: str, salt: str, modulo: int) -> int:
    digest = _stable_digest(session_id, region_id, salt)
    return int.from_bytes(digest[:4], "big") % modulo


def resolve_scene_category(direction_hint: str | None) -> GroundSceneCategory:
    if not direction_hint:
        return "generic_change"
    return _DIRECTION_TO_CATEGORY.get(direction_hint, "generic_change")


def resolve_direction_hint(region: EvidenceRegion, result: AnalysisResult) -> str | None:
    hint = region.metadata.get("change_direction_hint")
    if isinstance(hint, str) and hint:
        return hint
    bt = result.bi_temporal_change
    if bt and bt.detector_summary and bt.detector_summary.change_direction_hint:
        return bt.detector_summary.change_direction_hint
    return None


def deterministic_heading(session_id: str, region_id: str) -> float:
    return float(_stable_int(session_id, region_id, "heading", 360))


def deterministic_capture_date(
    session_id: str,
    region_id: str,
    *,
    later_acquisition: datetime | None,
) -> str:
    offset_days = _stable_int(session_id, region_id, "capture_date", 31)
    if later_acquisition is not None:
        anchor = later_acquisition.astimezone(UTC)
        capture = anchor - timedelta(days=offset_days)
        return capture.date().isoformat()
    fallback = datetime(2024, 6, 15, tzinfo=UTC) - timedelta(days=offset_days)
    return fallback.date().isoformat()


def build_ground_context(
    *,
    session_id: str,
    region: EvidenceRegion,
    result: AnalysisResult,
) -> GroundContextResult:
    lon, lat = polygon_centroid_wgs84(region.geometry.model_dump())
    direction_hint = resolve_direction_hint(region, result)
    category = resolve_scene_category(direction_hint)
    scene_def = _SCENE_DEFINITIONS[category]

    bt = result.bi_temporal_change
    later_dt: datetime | None = None
    if bt and bt.later_acquisition:
        later_dt = bt.later_acquisition

    return GroundContextResult(
        session_id=session_id,
        region_id=region.id,
        location=GroundContextLocation(latitude=lat, longitude=lon),
        heading=deterministic_heading(session_id, region.id),
        capture_date=deterministic_capture_date(
            session_id,
            region.id,
            later_acquisition=later_dt,
        ),
        scene=GroundContextScene(
            category=category,
            title=str(scene_def["title"]),
            description=str(scene_def["description"]),
            features=[str(feature) for feature in scene_def["features"]],  # type: ignore[arg-type]
        ),
        image=GroundContextImage(
            asset_id=str(scene_def["asset_id"]),
            url=str(scene_def["url"]),
            alt=str(scene_def["alt"]),
        ),
        provenance=GroundContextProvenance(),
    )


class MockGroundContextService:
    def __init__(self, store: SessionStore | None = None) -> None:
        self._store = store or session_store

    def get_ground_context(self, session_id: str, region_id: str) -> GroundContextResult:
        session = self._store.get(session_id)
        if not session or not session.result:
            raise SatQueryError(
                "session_not_found",
                f"No result for session: {session_id}",
                status_code=404,
            )

        result = session.result
        if not result.bi_temporal_change:
            raise SatQueryError(
                "not_bi_temporal_session",
                "Ground context requires a bi-temporal analysis session.",
                status_code=422,
            )

        region = _find_region(result, region_id)
        return build_ground_context(session_id=session_id, region=region, result=result)


mock_ground_context_service = MockGroundContextService()
