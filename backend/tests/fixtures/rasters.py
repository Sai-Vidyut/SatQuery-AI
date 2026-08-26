"""Helpers to create minimal raster fixtures for upload tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

_TAG_MODEL_PIXEL_SCALE = 33550
_TAG_MODEL_TIEPOINT = 33922
_TAG_GEO_KEY_DIRECTORY = 34735


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


def write_png(path: Path, *, width: int = 32, height: int = 32) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.zeros((height, width, 3), dtype=np.uint8)).save(path, format="PNG")


def write_jpeg(path: Path, *, width: int = 32, height: int = 32) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.zeros((height, width, 3), dtype=np.uint8)).save(path, format="JPEG")


def write_invalid_tiff(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not-a-tiff")
