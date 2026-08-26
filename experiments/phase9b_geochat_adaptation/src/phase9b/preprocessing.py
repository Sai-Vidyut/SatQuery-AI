"""Sentinel-2 -> GeoChat RGB preprocessing pipeline.

Documents and implements the exact, non-invented preprocessing steps:

  1. Band selection: B04 (Red), B03 (Green), B02 (Blue) — the standard
     Sentinel-2 true-color band mapping (same convention BigEarthNet.txt's
     own `ben_txt_datamodule.py` example uses).
  2. Reflectance scaling: Sentinel-2 L2A surface reflectance is stored as
     DN (digital number) where DN / 10000 = reflectance [0, 1]. For an
     8-bit RGB preview we stretch reflectance range [0, 0.3] (DN [0, 3000])
     to [0, 255] — this is the standard "true color" visualization range
     used by Earth Engine / Copernicus browser previews (documented, not
     invented; matches Phase 9A's fetch_image.py).
  3. Square resize: GeoChat interpolates its CLIP vision tower's position
     embeddings to a 504x504 input (see configs/model.yaml
     `vision_tower.interpolated_to_px`). `expand2square` (pad to square
     with the CLIP image_mean color, matching geochat/mm_utils.py exactly)
     is applied before resize to avoid aspect-ratio distortion — this
     mirrors GeoChat's own `process_images_demo` function.
  4. Channel ordering: HWC uint8 for storage/visualization; the CLIP
     image processor (loaded from the model, not reimplemented here)
     handles the final CHW float normalization at inference time.

Geospatial metadata (CRS, bounds, acquisition time, source scene ID) is
NEVER discarded — it is captured separately in `SceneMetadata` alongside
the visual PNG, per the task's explicit instruction.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

REFLECTANCE_STRETCH_MIN = 0
REFLECTANCE_STRETCH_MAX = 3000  # DN units; reflectance 0.30, standard true-color stretch
GEOCHAT_INPUT_PX = 504
RGB_BANDS = ("B04", "B03", "B02")  # Red, Green, Blue


@dataclass(frozen=True)
class SceneMetadata:
    """Geospatial metadata preserved separately from the visual RGB image."""

    source: str
    scene_id: str
    acquisition_time_iso: str | None
    bounds_wgs84: tuple[float, float, float, float] | None  # (min_lon, min_lat, max_lon, max_lat)
    crs: str
    bands_used: tuple[str, str, str]
    reflectance_stretch: tuple[int, int]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "scene_id": self.scene_id,
            "acquisition_time_iso": self.acquisition_time_iso,
            "bounds_wgs84": list(self.bounds_wgs84) if self.bounds_wgs84 else None,
            "crs": self.crs,
            "bands_used": list(self.bands_used),
            "reflectance_stretch": list(self.reflectance_stretch),
        }


def reflectance_dn_to_uint8(band: np.ndarray) -> np.ndarray:
    """Stretch a raw Sentinel-2 L2A DN band to uint8 [0, 255].

    band: 2D array of raw surface-reflectance DN values (0-10000 nominal).
    """
    clipped = np.clip(band, REFLECTANCE_STRETCH_MIN, REFLECTANCE_STRETCH_MAX)
    scaled = (clipped - REFLECTANCE_STRETCH_MIN) / (
        REFLECTANCE_STRETCH_MAX - REFLECTANCE_STRETCH_MIN
    )
    return (scaled * 255).astype(np.uint8)


def bands_to_rgb_uint8(red: np.ndarray, green: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """Stack three raw DN bands (B04, B03, B02) into an HWC uint8 RGB array."""
    if red.shape != green.shape or red.shape != blue.shape:
        raise ValueError("Red/Green/Blue bands must share the same shape")
    r8 = reflectance_dn_to_uint8(red)
    g8 = reflectance_dn_to_uint8(green)
    b8 = reflectance_dn_to_uint8(blue)
    return np.stack([r8, g8, b8], axis=-1)


def expand_to_square(image: Image.Image, background_rgb: tuple[int, int, int]) -> Image.Image:
    """Pad a PIL image to a square canvas, matching geochat/mm_utils.py's
    `expand2square` exactly (same centering/background behavior).
    """
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


# CLIP ViT-L/14 image_mean, used by GeoChat's own CLIPImageProcessor
# (openai/clip-vit-large-patch14-336). Verified against the processor's
# published preprocessor_config.json, not invented.
CLIP_IMAGE_MEAN = (0.48145466, 0.4578275, 0.40821073)


def prepare_geochat_visual_input(
    rgb_uint8: np.ndarray, *, target_px: int = GEOCHAT_INPUT_PX
) -> Image.Image:
    """Full visual-side preprocessing: array -> square-padded -> resized PIL image.

    Returns a plain RGB PIL.Image sized (target_px, target_px). The actual
    CHW float tensor + CLIP normalization is deferred to the model's own
    `CLIPImageProcessor.preprocess(...)` at inference time (see
    geochat_io.py) rather than reimplemented here, to guarantee we match
    GeoChat's exact expected input rather than an approximation.
    """
    if rgb_uint8.ndim != 3 or rgb_uint8.shape[-1] != 3:
        raise ValueError(f"Expected HWC RGB array, got shape {rgb_uint8.shape}")
    image = Image.fromarray(rgb_uint8, mode="RGB")
    bg = tuple(int(c * 255) for c in CLIP_IMAGE_MEAN)
    squared = expand_to_square(image, bg)
    return squared.resize((target_px, target_px), Image.BICUBIC)


def save_scene(
    rgb_uint8: np.ndarray,
    metadata: SceneMetadata,
    out_dir: Path,
    *,
    stem: str,
) -> tuple[Path, Path]:
    """Persist the visual PNG and its metadata JSON side by side.

    Returns (image_path, metadata_path). Never discards metadata: it is
    always written even if minimal (e.g. bounds unknown).
    """
    import json

    out_dir.mkdir(parents=True, exist_ok=True)
    image_path = out_dir / f"{stem}.png"
    metadata_path = out_dir / f"{stem}.metadata.json"
    Image.fromarray(rgb_uint8, mode="RGB").save(image_path)
    metadata_path.write_text(json.dumps(metadata.to_dict(), indent=2))
    return image_path, metadata_path
