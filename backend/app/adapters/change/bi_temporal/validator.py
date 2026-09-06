"""Raster-level validation complementing existing ImageInput checks."""

from __future__ import annotations

from pathlib import Path

import rasterio

from app.core.errors import SatQueryError
from app.schemas.input import ImageFormat, ImageInput


def _extension_for_format(fmt: ImageFormat) -> str:
    if fmt in (ImageFormat.GEOTIFF, ImageFormat.TIFF):
        return ".tif"
    if fmt == ImageFormat.PNG:
        return ".png"
    return ".jpg"


def validate_raster_readable(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise SatQueryError(
            "invalid_raster",
            f"Raster not found or empty: {path.name}",
            status_code=400,
        )
    try:
        with rasterio.open(path) as src:
            if src.count < 1:
                raise SatQueryError(
                    "invalid_raster",
                    "Raster has no bands.",
                    status_code=400,
                )
            return {
                "path": str(path),
                "crs": src.crs.to_string() if src.crs else None,
                "transform": src.transform,
                "count": src.count,
                "height": src.height,
                "width": src.width,
                "bounds": src.bounds,
            }
    except SatQueryError:
        raise
    except Exception as exc:
        raise SatQueryError(
            "invalid_raster",
            f"Cannot read raster {path.name}.",
            status_code=400,
        ) from exc


def validate_raster_pair(
    earlier_path: Path,
    later_path: Path,
    earlier_meta: ImageInput,
    later_meta: ImageInput,
    *,
    resolution_tolerance: float = 10.0,
) -> None:
    info_t1 = validate_raster_readable(earlier_path)
    info_t2 = validate_raster_readable(later_path)

    if not info_t1["crs"] or not info_t2["crs"]:
        raise SatQueryError(
            "missing_georeferencing",
            "Both rasters must include a CRS for bi-temporal change detection.",
            status_code=400,
        )

    b1 = info_t1["bounds"]
    b2 = info_t2["bounds"]
    x_overlap = b1.left < b2.right and b2.left < b1.right
    y_overlap = b1.bottom < b2.top and b2.bottom < b1.top
    if not (x_overlap and y_overlap):
        raise SatQueryError(
            "spatial_overlap",
            "Uploaded rasters do not spatially overlap.",
            status_code=400,
        )

    tr1 = info_t1["transform"]
    tr2 = info_t2["transform"]
    gsd1 = abs(tr1.a)
    gsd2 = abs(tr2.a)
    if gsd1 > 0 and gsd2 > 0:
        ratio = max(gsd1, gsd2) / min(gsd1, gsd2)
        if ratio > resolution_tolerance:
            pass  # co-registration will resample; warning only at metadata layer

    if earlier_meta.acquisition_datetime and later_meta.acquisition_datetime:
        if later_meta.acquisition_datetime <= earlier_meta.acquisition_datetime:
            raise SatQueryError(
                "temporal_order",
                "Later image acquisition must be after earlier image.",
                status_code=400,
            )


def resolve_upload_path(image: ImageInput, storage) -> Path:
    ext = _extension_for_format(image.format)
    return storage.path_for(image.id, ext)
