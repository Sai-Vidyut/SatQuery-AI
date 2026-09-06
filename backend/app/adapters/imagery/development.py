from __future__ import annotations

import hashlib
from datetime import date

from app.schemas.domain import (
    DataMode,
    ImageryRequest,
    ImageryResult,
    ImageryScene,
    SensorType,
    SpatialMetadata,
)
from app.adapters.imagery.base import ImageryProvider


def _bbox_from_polygon(coords: list) -> list[float]:
    """Extract bbox from GeoJSON polygon outer ring."""
    ring = coords[0] if coords else []
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return [min(lons), min(lats), max(lons), max(lats)]


def _deterministic_cloud(seed: str, acquisition: date) -> float:
    digest = hashlib.sha256(f"{seed}:{acquisition.isoformat()}".encode()).hexdigest()
    return round(int(digest[:4], 16) / 65535 * 25, 1)


class DevelopmentImageryProvider(ImageryProvider):
    """
    Isolated development adapter. Does NOT claim Earth Engine or real Sentinel access.
    Returns reproducible metadata for local demos and tests.
    """

    @property
    def name(self) -> str:
        return "development"

    async def fetch(self, request: ImageryRequest) -> ImageryResult:
        bbox = _bbox_from_polygon(request.aoi.geometry.coordinates)
        seed = hashlib.sha256(str(bbox).encode()).hexdigest()[:12]

        scenes: list[ImageryScene] = []
        for acquisition in (request.start_date, request.end_date):
            scenes.append(
                ImageryScene(
                    scene_id=f"dev-{request.sensor.value}-{seed}-{acquisition.isoformat()}",
                    acquisition_date=acquisition,
                    cloud_cover_percent=_deterministic_cloud(seed, acquisition),
                    preview_url=None,
                )
            )

        resolution = 10.0 if request.sensor == SensorType.SENTINEL_2 else 20.0

        return ImageryResult(
            source="satquery-development-imagery",
            mode=DataMode.DEVELOPMENT,
            sensor=request.sensor,
            scenes=scenes,
            spatial=SpatialMetadata(bbox=bbox, resolution_m=resolution),
            message=(
                "DEMONSTRATION DATA: development imagery adapter with deterministic scene metadata. "
                "Not real Earth observation."
            ),
            provider_metadata={
                "demonstration_data": True,
                "imagery_strategy": "development_fixture",
                "t1": {
                    "requested_date": request.start_date.isoformat(),
                    "window_start": request.start_date.isoformat(),
                    "window_end": request.start_date.isoformat(),
                    "scene_count": 1,
                },
                "t2": {
                    "requested_date": request.end_date.isoformat(),
                    "window_start": request.end_date.isoformat(),
                    "window_end": request.end_date.isoformat(),
                    "scene_count": 1,
                },
            },
        )
