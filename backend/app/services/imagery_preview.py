"""Render PNG previews from uploaded georeferenced rasters."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

from app.core.errors import SatQueryError


def parse_bbox_wgs84(bbox: str) -> tuple[float, float, float, float]:
    """Parse minx,miny,maxx,maxy in WGS84 degrees."""
    parts = [part.strip() for part in bbox.split(",")]
    if len(parts) != 4:
        raise SatQueryError(
            "invalid_preview_bbox",
            "bbox must be minx,miny,maxx,maxy in WGS84 degrees.",
            status_code=422,
            field="bbox",
        )
    try:
        minx, miny, maxx, maxy = (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
    except ValueError as exc:
        raise SatQueryError(
            "invalid_preview_bbox",
            "bbox coordinates must be numeric.",
            status_code=422,
            field="bbox",
        ) from exc

    if minx >= maxx or miny >= maxy:
        raise SatQueryError(
            "invalid_preview_bbox",
            "bbox min coordinates must be less than max coordinates.",
            status_code=422,
            field="bbox",
        )
    if not (-180.0 <= minx <= 180.0 and -180.0 <= maxx <= 180.0 and -90.0 <= miny <= 90.0 and -90.0 <= maxy <= 90.0):
        raise SatQueryError(
            "invalid_preview_bbox",
            "bbox coordinates are out of WGS84 range.",
            status_code=422,
            field="bbox",
        )
    return (minx, miny, maxx, maxy)


def _intersect_bounds(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    left = max(a[0], b[0])
    bottom = max(a[1], b[1])
    right = min(a[2], b[2])
    top = min(a[3], b[3])
    if left >= right or bottom >= top:
        return None
    return (left, bottom, right, top)


def _to_rgb_uint8(data: np.ndarray) -> np.ndarray:
    if data.ndim == 2:
        data = data[np.newaxis, ...]
    bands, _height, _width = data.shape
    arr = data.astype(np.float32)

    if bands >= 3:
        # Sentinel-like order (B2,B3,B4,...) → display R=B4, G=B3, B=B2
        red = arr[2] if bands > 2 else arr[0]
        green = arr[1] if bands > 1 else arr[0]
        blue = arr[0]
        rgb = np.stack([red, green, blue], axis=-1)
    else:
        gray = arr[0]
        rgb = np.stack([gray, gray, gray], axis=-1)

    finite = rgb[np.isfinite(rgb)]
    if finite.size == 0:
        return np.zeros(rgb.shape, dtype=np.uint8)

    lo = float(np.percentile(finite, 2))
    hi = float(np.percentile(finite, 98))
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((rgb - lo) / (hi - lo), 0.0, 1.0)
    return (scaled * 255.0).astype(np.uint8)


def _crop_bounds_in_src_crs(
    src: rasterio.io.DatasetReader,
    bbox_wgs84: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    if src.crs is None:
        raise SatQueryError(
            "missing_georeferencing",
            "Raster must include georeferencing for preview.",
            status_code=400,
        )

    rb = src.bounds
    looks_geographic = (
        abs(rb.left) <= 180
        and abs(rb.right) <= 180
        and abs(rb.bottom) <= 90
        and abs(rb.top) <= 90
        and abs(rb.right - rb.left) < 360
    )

    if src.crs.to_epsg() == 4326 or getattr(src.crs, "is_geographic", False) or looks_geographic:
        return bbox_wgs84

    return transform_bounds(CRS.from_epsg(4326), src.crs, *bbox_wgs84)


def render_raster_preview_png(
    path: Path,
    *,
    bbox_wgs84: tuple[float, float, float, float],
    max_size: int = 512,
) -> bytes:
    """Crop raster to WGS84 bbox (with CRS transform) and return PNG bytes."""
    if max_size < 64 or max_size > 2048:
        raise SatQueryError(
            "invalid_preview_size",
            "max_size must be between 64 and 2048.",
            status_code=422,
            field="max_size",
        )

    try:
        with rasterio.open(path) as src:
            crop_bounds = _crop_bounds_in_src_crs(src, bbox_wgs84)

            raster_bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
            intersected = _intersect_bounds(crop_bounds, raster_bounds)
            if intersected is None:
                raise SatQueryError(
                    "preview_bbox_no_intersection",
                    "Requested bbox does not intersect the raster extent.",
                    status_code=422,
                    field="bbox",
                )

            window = from_bounds(*intersected, transform=src.transform)
            full = Window(0, 0, src.width, src.height)
            window = window.intersection(full)
            if window.width <= 0 or window.height <= 0:
                raise SatQueryError(
                    "preview_bbox_no_intersection",
                    "Requested bbox does not intersect the raster extent.",
                    status_code=422,
                    field="bbox",
                )

            data = src.read(window=window)
    except SatQueryError:
        raise
    except Exception as exc:
        raise SatQueryError(
            "preview_render_failed",
            "Failed to render raster preview.",
            status_code=500,
        ) from exc

    rgb = _to_rgb_uint8(data)
    image = Image.fromarray(rgb, mode="RGB")

    width, height = image.size
    if width > max_size or height > max_size:
        if width >= height:
            new_w = max_size
            new_h = max(1, int(round(height * (max_size / width))))
        else:
            new_h = max_size
            new_w = max(1, int(round(width * (max_size / height))))
        image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
