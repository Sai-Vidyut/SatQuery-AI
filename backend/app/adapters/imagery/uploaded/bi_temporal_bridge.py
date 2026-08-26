"""Bridge uploaded bi-temporal ImageInput pairs to existing CVA contracts."""

from __future__ import annotations

from datetime import date

from app.schemas.domain import (
    AOI,
    ChangeDetectionInput,
    DataMode,
    GeoJSONGeometry,
    ImageryResult,
    ImageryScene,
    SensorType,
    SpatialMetadata,
)
from app.schemas.input import ImageInput


def _intersection_bounds(a: list[float], b: list[float]) -> list[float]:
    west = max(a[0], b[0])
    south = max(a[1], b[1])
    east = min(a[2], b[2])
    north = min(a[3], b[3])
    return [west, south, east, north]


def aoi_from_bounds(bounds: list[float]) -> AOI:
    west, south, east, north = bounds
    return AOI(
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],
                ]
            ],
        )
    )


def build_imagery_result_from_pair(earlier: ImageInput, later: ImageInput) -> ImageryResult:
    bounds = earlier.bounds
    if earlier.bounds and later.bounds:
        bounds = _intersection_bounds(earlier.bounds, later.bounds)
    return ImageryResult(
        source="uploaded",
        mode=DataMode.DEVELOPMENT,
        sensor=SensorType.SENTINEL_2,
        scenes=[
            ImageryScene(
                scene_id=earlier.id,
                acquisition_date=earlier.acquisition_datetime.date()
                if earlier.acquisition_datetime
                else date(1970, 1, 1),
                platform_id=f"upload://{earlier.id}",
                metadata={"filename": earlier.filename, "role": "earlier"},
            ),
            ImageryScene(
                scene_id=later.id,
                acquisition_date=later.acquisition_datetime.date()
                if later.acquisition_datetime
                else date(1970, 1, 1),
                platform_id=f"upload://{later.id}",
                metadata={"filename": later.filename, "role": "later"},
            ),
        ],
        spatial=SpatialMetadata(
            crs=earlier.crs or later.crs or "EPSG:4326",
            bbox=bounds or [0.0, 0.0, 0.01, 0.01],
        ),
        collection_id="uploaded_bi_temporal",
        message="Uploaded bi-temporal pair — development CVA adapter.",
    )


def build_change_detection_input(earlier: ImageInput, later: ImageInput) -> ChangeDetectionInput:
    if not earlier.acquisition_datetime or not later.acquisition_datetime:
        raise ValueError("Both images must include acquisition_datetime for bi-temporal CVA.")
    bounds = earlier.bounds or later.bounds
    if earlier.bounds and later.bounds:
        bounds = _intersection_bounds(earlier.bounds, later.bounds)
    if not bounds:
        raise ValueError("Both images must include geographic bounds for bi-temporal CVA.")
    return ChangeDetectionInput(
        aoi=aoi_from_bounds(bounds),
        earlier_date=earlier.acquisition_datetime.date(),
        later_date=later.acquisition_datetime.date(),
        imagery=build_imagery_result_from_pair(earlier, later),
    )
