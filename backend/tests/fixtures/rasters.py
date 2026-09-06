"""Helpers to create minimal and multispectral raster fixtures for upload tests."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import tifffile
from PIL import Image

_TAG_MODEL_PIXEL_SCALE = 33550
_TAG_MODEL_TIEPOINT = 33922
_TAG_GEO_KEY_DIRECTORY = 34735

ScenarioName = Literal["vegetation_loss", "flood", "urban", "pseudo_change", "uniform"]
SceneRole = Literal["earlier", "later"]

SENTINEL2_BAND_NAMES = ["B2", "B3", "B4", "B8", "B11"]


def write_geotiff(
    path: Path,
    *,
    width: int = 64,
    height: int = 64,
    origin_lon: float = 77.59,
    origin_lat: float = 12.99,
    pixel_size: float = 0.0001,
    epsg: int = 4326,
    bands: int = 1,
) -> None:
    """Single-band GeoTIFF (legacy helper for VQA/upload smoke tests)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if bands == 1:
        data = np.zeros((height, width), dtype=np.uint16)
    else:
        data = np.zeros((bands, height, width), dtype=np.uint16)

    geokeys = (1, 1, 0, 1, 2048, 0, 1, epsg)
    extratags = [
        (_TAG_MODEL_PIXEL_SCALE, "d", 3, (pixel_size, pixel_size, 0.0), False),
        (_TAG_MODEL_TIEPOINT, "d", 6, (0.0, 0.0, 0.0, origin_lon, origin_lat, 0.0), False),
        (_TAG_GEO_KEY_DIRECTORY, "H", len(geokeys), geokeys, False),
    ]
    tifffile.imwrite(path, data, extratags=extratags)


def _make_optical_array(
    *,
    width: int,
    height: int,
    ndvi_value: float = 0.5,
    ndwi_value: float = -0.2,
) -> np.ndarray:
    """Band order: Blue, Green, Red, NIR, SWIR (Sentinel-2-like)."""
    arr = np.zeros((5, height, width), dtype=np.float32)
    nir = 0.6
    red = nir * (1.0 - ndvi_value) / (1.0 + ndvi_value)
    green = max(0.05, (ndwi_value + 1.0) * nir / max(1.0 - ndwi_value, 1e-3))
    arr[0] = 0.05
    arr[1] = float(green)
    arr[2] = float(red)
    arr[3] = float(nir)
    arr[4] = 0.2
    return arr


def _scenario_arrays(
    scenario: ScenarioName,
    *,
    width: int = 64,
    height: int = 64,
) -> tuple[np.ndarray, np.ndarray]:
    t1 = _make_optical_array(width=width, height=height, ndvi_value=0.55, ndwi_value=-0.25)
    t2 = t1.copy()
    cy, cx = height // 2, width // 2
    y0, y1 = max(0, cy - 12), min(height, cy + 12)
    x0, x1 = max(0, cx - 12), min(width, cx + 12)

    if scenario == "vegetation_loss":
        t2[3, y0:y1, x0:x1] *= 0.25
        t2[2, y0:y1, x0:x1] *= 1.15
    elif scenario == "flood":
        t2[1, y0:y1, x0:x1] *= 1.8
        t2[3, y0:y1, x0:x1] *= 0.55
    elif scenario == "urban":
        t2[4, y0:y1, x0:x1] *= 1.9
        t2[3, y0:y1, x0:x1] *= 0.7
    elif scenario == "pseudo_change":
        t2 = t1 * 1.15 + 0.08
        t2[4, y0:y1, x0:x1] *= 2.5
        t2[3, y0:y1, x0:x1] *= 0.6
    elif scenario == "uniform":
        pass
    return t1, t2


def write_multispectral_geotiff(
    path: Path,
    array: np.ndarray,
    *,
    origin_lon: float = 77.59,
    origin_lat: float = 12.99,
    pixel_size: float = 0.0001,
    epsg: int = 4326,
) -> None:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin

    path.parent.mkdir(parents=True, exist_ok=True)
    if array.ndim == 2:
        array = array[np.newaxis, ...]
    scaled = np.clip(array * 10_000.0, 0, 65535).astype(np.uint16)
    transform = from_origin(origin_lon, origin_lat, pixel_size, pixel_size)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=scaled.shape[1],
        width=scaled.shape[2],
        count=scaled.shape[0],
        dtype="uint16",
        crs=CRS.from_epsg(epsg),
        transform=transform,
    ) as dst:
        dst.write(scaled)


def write_bi_temporal_scene(
    path: Path,
    *,
    role: SceneRole,
    scenario: ScenarioName = "vegetation_loss",
    width: int = 64,
    height: int = 64,
    origin_lon: float = 77.59,
    origin_lat: float = 12.99,
    pixel_size: float = 0.0001,
) -> None:
    t1, t2 = _scenario_arrays(scenario, width=width, height=height)
    array = t1 if role == "earlier" else t2
    write_multispectral_geotiff(
        path,
        array,
        origin_lon=origin_lon,
        origin_lat=origin_lat,
        pixel_size=pixel_size,
    )


def write_png(path: Path, *, width: int = 32, height: int = 32) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.zeros((height, width, 3), dtype=np.uint8)).save(path, format="PNG")


def write_jpeg(path: Path, *, width: int = 32, height: int = 32) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.zeros((height, width, 3), dtype=np.uint8)).save(path, format="JPEG")


def write_invalid_tiff(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not-a-tiff")
