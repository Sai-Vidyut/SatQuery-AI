"""Load single-scene or median-composite Sentinel-2 epochs for change detection."""

from __future__ import annotations

from typing import Any

from app.adapters.change.earth_engine.cloud_mask import mask_sentinel2_sr
from app.adapters.change.earth_engine.constants import CVA_BANDS
from app.adapters.change.earth_engine.cva import load_scene_image
from app.adapters.imagery.earth_engine.composite import is_composite_scene
from app.core.errors import SatQueryError
from app.schemas.domain import ImageryScene

_MIN_VALID_PIXELS = 1


def _mask_and_select_bands(image: Any, ee: Any) -> Any:
    return mask_sentinel2_sr(image, ee).select(CVA_BANDS)


def build_median_composite_image(ee: Any, platform_ids: list[str]) -> Any:
    """Median composite of cloud-masked Sentinel-2 SR scenes."""
    if not platform_ids:
        raise SatQueryError(
            "insufficient_imagery",
            "Composite epoch has no source scenes.",
            status_code=400,
        )
    prepared = [_mask_and_select_bands(load_scene_image(ee, pid), ee) for pid in platform_ids]
    if len(prepared) == 1:
        return prepared[0]
    return ee.ImageCollection.fromImages(prepared).median()


def load_epoch_image(ee: Any, scene: ImageryScene) -> Any:
    """Load a single scene or median composite for one temporal epoch."""
    if is_composite_scene(scene):
        platform_ids = (scene.metadata or {}).get("scene_platform_ids") or []
        if not platform_ids:
            raise SatQueryError(
                "invalid_imagery_metadata",
                f"Composite scene '{scene.scene_id}' is missing scene_platform_ids.",
                status_code=400,
                field="imagery.scenes",
            )
        return build_median_composite_image(ee, platform_ids)
    if not scene.platform_id:
        raise SatQueryError(
            "invalid_imagery_metadata",
            f"Scene '{scene.scene_id}' is missing platform_id.",
            status_code=400,
            field="imagery.scenes",
        )
    return _mask_and_select_bands(load_scene_image(ee, scene.platform_id), ee)


def validate_epoch_coverage(
    ee: Any,
    image: Any,
    aoi_geometry: Any,
    *,
    epoch_label: str,
    scale: float = 10.0,
) -> None:
    """Fail clearly when masking leaves no valid pixels in the AOI."""
    try:
        count = (
            image.mask()
            .reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=aoi_geometry,
                scale=scale,
                maxPixels=1e9,
                bestEffort=True,
                tileScale=4,
            )
            .getInfo()
        )
        total = sum(float(v) for v in (count or {}).values() if v is not None)
    except Exception as exc:
        raise SatQueryError(
            "earth_engine_request_failed",
            f"Failed to validate {epoch_label} composite coverage: {exc}",
            status_code=502,
        ) from exc

    if total < _MIN_VALID_PIXELS:
        raise SatQueryError(
            "insufficient_imagery",
            f"{epoch_label} composite has no valid pixels after cloud masking in the AOI. "
            "Try widening the composite window or increasing cloud_cover_max.",
            status_code=404,
        )
