"""Bridge uploaded optical+SAR pairs to shared AOI / imagery contracts."""

from __future__ import annotations

from datetime import date

from app.adapters.imagery.uploaded.bi_temporal_bridge import _intersection_bounds, aoi_from_bounds
from app.schemas.domain import (
    AOI,
    DataMode,
    ImageryResult,
    ImageryScene,
    SensorType,
    SpatialMetadata,
)
from app.schemas.input import ImageInput


def pair_bounds(optical: ImageInput, sar: ImageInput) -> list[float]:
    if optical.bounds and sar.bounds:
        return _intersection_bounds(optical.bounds, sar.bounds)
    if optical.bounds:
        return optical.bounds
    if sar.bounds:
        return sar.bounds
    if optical.benchmark_dataset and sar.benchmark_dataset:
        # Benchmark JPEG/PNG without georeferencing — development-only neutral extent.
        return [0.0, 0.0, 0.01, 0.01]
    raise ValueError("Both images must include geographic bounds for cross-modal analysis.")


def build_cross_modal_imagery_result(optical: ImageInput, sar: ImageInput) -> ImageryResult:
    bounds = pair_bounds(optical, sar)
    acq = optical.acquisition_datetime or sar.acquisition_datetime
    acq_date = acq.date() if acq else date(1970, 1, 1)
    return ImageryResult(
        source="uploaded_cross_modal",
        mode=DataMode.DEVELOPMENT,
        sensor=SensorType.SENTINEL_2,
        scenes=[
            ImageryScene(
                scene_id=optical.id,
                acquisition_date=acq_date,
                platform_id=f"upload://{optical.id}",
                metadata={"filename": optical.filename, "role": "optical"},
            ),
            ImageryScene(
                scene_id=sar.id,
                acquisition_date=acq_date,
                platform_id=f"upload://{sar.id}",
                metadata={"filename": sar.filename, "role": "sar"},
            ),
        ],
        spatial=SpatialMetadata(crs=optical.crs or sar.crs or "EPSG:4326", bbox=bounds),
        collection_id="uploaded_optical_sar_pair",
        message="Uploaded cross-modal optical+SAR pair — development adapters.",
    )


def pair_aoi(optical: ImageInput, sar: ImageInput) -> AOI:
    return aoi_from_bounds(pair_bounds(optical, sar))
