"""Test fixtures for GeoChat service tests."""

from __future__ import annotations

import base64
import io

import numpy as np
import tifffile
from PIL import Image


def _tiny_geotiff_bytes() -> bytes:
    data = np.zeros((32, 32), dtype=np.uint16)
    buf = io.BytesIO()
    tifffile.imwrite(buf, data)
    return buf.getvalue()


def make_image_bytes() -> dict:
    return {
        "content_base64": base64.b64encode(_tiny_geotiff_bytes()).decode("ascii"),
        "format": "geotiff",
        "filename": "scene.tif",
    }


def make_metadata() -> dict:
    return {
        "image_id": "a" * 32,
        "modality": "optical",
        "width": 32,
        "height": 32,
        "georeferenced": True,
        "crs": "EPSG:4326",
        "bounds": [77.59, 12.99, 77.5964, 12.9964],
    }
