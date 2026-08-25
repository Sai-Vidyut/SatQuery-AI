from __future__ import annotations

from typing import Any

from app.adapters.change.earth_engine.cloud_mask import mask_sentinel2_sr
from app.adapters.change.earth_engine.constants import CVA_BANDS


def load_scene_image(ee: Any, platform_id: str) -> Any:
    return ee.Image(platform_id)


def prepare_scene(image: Any, ee: Any) -> Any:
    masked = mask_sentinel2_sr(image, ee)
    return masked.select(CVA_BANDS)


def compute_change_magnitude(before: Any, after: Any, ee: Any) -> Any:
    """Euclidean distance in multispectral space (Change Vector Analysis magnitude)."""
    combined_mask = before.mask().And(after.mask())
    b = before.updateMask(combined_mask)
    a = after.updateMask(combined_mask)
    diff = b.subtract(a)
    return diff.pow(2).reduce(ee.Reducer.sum()).sqrt().rename("change_magnitude")
