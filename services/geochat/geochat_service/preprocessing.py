"""Raster preprocessing for GeoChat 504x504 RGB input (Phase 9B rules)."""

from __future__ import annotations

import base64
import io
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from geochat_service.schemas import GeoChatImageBytes, GeoChatImageMetadata

REFLECTANCE_STRETCH_MIN = 0
REFLECTANCE_STRETCH_MAX = 3000
GEOCHAT_INPUT_PX = 504
CLIP_IMAGE_MEAN = (0.48145466, 0.4578275, 0.40821073)


def expand_to_square(image: Image.Image, background_rgb: tuple[int, int, int]) -> Image.Image:
    width, height = image.size
    if width == height:
        return image
    if width > height:
        result = Image.new(image.mode, (width, width), background_rgb)
        result.paste(image, (0, (width - height) // 2))
        return result
    result = Image.new(image.mode, (height, height), background_rgb)
    result.paste(image, ((height - width) // 2, 0))
    return result


def _uint8_band(band: np.ndarray) -> np.ndarray:
    clipped = np.clip(band, REFLECTANCE_STRETCH_MIN, REFLECTANCE_STRETCH_MAX)
    scaled = (clipped - REFLECTANCE_STRETCH_MIN) / (
        REFLECTANCE_STRETCH_MAX - REFLECTANCE_STRETCH_MIN
    )
    return (scaled * 255).astype(np.uint8)


def _geotiff_to_rgb_uint8(raw: bytes) -> np.ndarray:
    import tifffile

    data = tifffile.imread(io.BytesIO(raw))
    if data.ndim == 2:
        band = _uint8_band(data.astype(np.float64))
        return np.stack([band, band, band], axis=-1)
    if data.ndim == 3:
        if data.shape[0] in (1, 3, 4) and data.shape[0] <= 4:
            planes = data
            if planes.shape[0] == 1:
                band = _uint8_band(planes[0].astype(np.float64))
                return np.stack([band, band, band], axis=-1)
            rgb = np.stack(
                [
                    _uint8_band(planes[0].astype(np.float64)),
                    _uint8_band(planes[1].astype(np.float64)),
                    _uint8_band(planes[2].astype(np.float64)),
                ],
                axis=-1,
            )
            return rgb
        if data.shape[-1] in (1, 3, 4):
            if data.shape[-1] == 1:
                band = _uint8_band(data[..., 0].astype(np.float64))
                return np.stack([band, band, band], axis=-1)
            return np.stack(
                [
                    _uint8_band(data[..., 0].astype(np.float64)),
                    _uint8_band(data[..., 1].astype(np.float64)),
                    _uint8_band(data[..., 2].astype(np.float64)),
                ],
                axis=-1,
            )
    raise ValueError(f"Unsupported GeoTIFF shape for GeoChat preprocessing: {data.shape}")


def _pil_from_bytes(image: GeoChatImageBytes) -> Image.Image:
    raw = base64.b64decode(image.content_base64)
    if image.format in {"geotiff", "tiff"}:
        rgb = _geotiff_to_rgb_uint8(raw)
        return Image.fromarray(rgb, mode="RGB")
    return Image.open(io.BytesIO(raw)).convert("RGB")


def prepare_geochat_image(
    image: GeoChatImageBytes,
    metadata: GeoChatImageMetadata,
) -> tuple[Image.Image, dict]:
    """Decode bytes and produce a 504x504 RGB PIL image for GeoChat inference."""
    pil = _pil_from_bytes(image)
    bg = tuple(int(c * 255) for c in CLIP_IMAGE_MEAN)
    squared = expand_to_square(pil, bg)
    prepared = squared.resize((GEOCHAT_INPUT_PX, GEOCHAT_INPUT_PX), Image.BICUBIC)
    preprocess_meta = {
        "source_format": image.format,
        "source_filename": image.filename,
        "source_width": metadata.width,
        "source_height": metadata.height,
        "output_px": GEOCHAT_INPUT_PX,
        "reflectance_stretch": [REFLECTANCE_STRETCH_MIN, REFLECTANCE_STRETCH_MAX],
        "image_id": metadata.image_id,
        "modality": metadata.modality,
    }
    return prepared, preprocess_meta
