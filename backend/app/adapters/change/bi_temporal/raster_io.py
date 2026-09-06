"""GeoTIFF loading, co-registration, and polygonization for uploaded pairs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from app.core.errors import SatQueryError
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.features import shapes as rasterio_shapes
from rasterio.warp import calculate_default_transform, reproject, transform_geom
from shapely.geometry import mapping, shape


@dataclass
class RasterData:
    array: np.ndarray
    meta: dict[str, Any]
    path: str | None = None

    @property
    def bands(self) -> int:
        return int(self.array.shape[0])

    @property
    def height(self) -> int:
        return int(self.array.shape[1])

    @property
    def width(self) -> int:
        return int(self.array.shape[2])

    @property
    def crs(self) -> CRS | None:
        return self.meta.get("crs")

    @property
    def transform(self):
        return self.meta.get("transform")


from app.core.errors import SatQueryError


def load_raster(path: str | Path) -> RasterData:
    path = str(path)
    try:
        with rasterio.open(path) as src:
            array = src.read().astype(np.float32)
            if array.ndim == 2:
                array = array[np.newaxis, ...]
            if array.size and float(np.nanmax(array)) > 1.5:
                array = array / 10_000.0
            meta = src.profile.copy()
            meta["count"] = array.shape[0]
        return RasterData(array=array, meta=meta, path=path)
    except SatQueryError:
        raise
    except Exception as exc:
        raise SatQueryError(
            "invalid_raster",
            f"Unable to load raster {Path(path).name}.",
            status_code=400,
        ) from exc


def needs_coregistration(reference: RasterData, source: RasterData) -> bool:
    return (
        reference.crs != source.crs
        or reference.transform != source.transform
        or reference.height != source.height
        or reference.width != source.width
    )


def match_raster(source: RasterData, reference: RasterData) -> RasterData:
    """Reproject/resample source to reference grid."""
    try:
        dst_array = np.zeros((source.bands, reference.height, reference.width), dtype=np.float32)
        for band_idx in range(source.bands):
            reproject(
                source=source.array[band_idx],
                destination=dst_array[band_idx],
                src_transform=source.transform,
                src_crs=source.crs,
                dst_transform=reference.transform,
                dst_crs=reference.crs,
                resampling=Resampling.bilinear,
            )
        new_meta = source.meta.copy()
        new_meta.update(
            {
                "crs": reference.crs,
                "transform": reference.transform,
                "height": reference.height,
                "width": reference.width,
            }
        )
        return RasterData(array=dst_array, meta=new_meta, path=source.path)
    except Exception as exc:
        raise SatQueryError(
            "coregistration_failed",
            "Failed to co-register uploaded bi-temporal rasters.",
            status_code=500,
        ) from exc


def polygonize_mask(
    mask: np.ndarray,
    reference: RasterData,
    *,
    min_area_px: int = 4,
) -> list[dict[str, Any]]:
    """Return GeoJSON-like polygon dicts in WGS84 coordinates."""
    try:
        mask_u8 = mask.astype(np.uint8)
        transform = reference.transform
        crs = reference.crs
        pixel_area = abs(float(transform.a * transform.e)) if transform else 1.0
        if pixel_area < 1e-12:
            pixel_area = 1.0

        features: list[dict[str, Any]] = []
        for geom_dict, value in rasterio_shapes(mask_u8, transform=transform):
            if value == 0:
                continue
            geom = shape(geom_dict)
            approx_px = geom.area / pixel_area
            if approx_px < min_area_px:
                continue

            if crs and crs.to_epsg() and crs.to_epsg() != 4326:
                geom_dict = transform_geom(
                    crs,
                    "EPSG:4326",
                    mapping(geom),
                    precision=6,
                )
            else:
                geom_dict = mapping(geom)

            features.append(
                {
                    "geometry": geom_dict,
                    "properties": {
                        "area_px": round(float(approx_px), 1),
                    },
                }
            )
        return features
    except SatQueryError:
        raise
    except Exception as exc:
        raise SatQueryError(
            "polygonization_failed",
            "Failed to polygonize bi-temporal change mask.",
            status_code=500,
        ) from exc


def bounds_wgs84(reference: RasterData) -> tuple[float, float, float, float]:
    left, bottom, right, top = rasterio.transform.array_bounds(
        reference.height,
        reference.width,
        reference.transform,
    )
    if reference.crs and reference.crs.to_epsg() not in (None, 4326):
        from rasterio.warp import transform_bounds

        return transform_bounds(reference.crs, "EPSG:4326", left, bottom, right, top)
    return (left, bottom, right, top)
