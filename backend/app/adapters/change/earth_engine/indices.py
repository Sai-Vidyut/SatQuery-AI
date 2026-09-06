"""Spectral index computation for Earth Engine Sentinel-2 change detection (Phase 7)."""

from __future__ import annotations

from typing import Any

from app.adapters.change.bi_temporal.indices import select_primary_index
from app.schemas.change_domain import ChangeDomain

# Domain → default primary index (mirrors upload path / Phase 5B alignment).
_DOMAIN_INDEX_MAP: dict[ChangeDomain, str] = {
    ChangeDomain.DEFORESTATION: "ndvi",
    ChangeDomain.WATER_SHRINKAGE: "ndwi",
    ChangeDomain.URBAN_EXPANSION: "ndbi",
    ChangeDomain.INFRASTRUCTURE_DEVELOPMENT: "ndbi",
    ChangeDomain.MINING: "ndvi",
}

# Sentinel-2 SR band roles for index computation (bands already in CVA_BANDS).
_OPTICAL_BAND_COUNT = 6
_OPTICAL_BAND_MAP = {"blue": 0, "green": 1, "red": 2, "nir": 3, "swir": 4}


def select_primary_index_for_catalog(
    *,
    change_domain: ChangeDomain | None = None,
    query_hint: str | None = None,
) -> str | None:
    """
    Return primary index for domain-aware catalog detection, or None for generic CVA.

    Uses domain map first, then query-hint routing (same as upload path).
    """
    if change_domain is not None:
        domain_index = _DOMAIN_INDEX_MAP.get(change_domain)
        if domain_index:
            return domain_index

    if query_hint:
        hint_index = select_primary_index(
            _OPTICAL_BAND_COUNT,
            _OPTICAL_BAND_MAP,
            modality="optical",
            query_hint=query_hint,
        )
        if hint_index in ("ndvi", "ndwi", "ndbi"):
            return hint_index

    return None


def compute_index(image: Any, index_name: str, ee: Any) -> Any:
    """Compute a normalized difference index from masked Sentinel-2 SR image."""
    name = index_name.lower()
    if name == "ndvi":
        nir = image.select("B8")
        red = image.select("B4")
        return nir.subtract(red).divide(nir.add(red)).rename("index")
    if name == "ndwi":
        green = image.select("B3")
        nir = image.select("B8")
        return green.subtract(nir).divide(green.add(nir)).rename("index")
    if name == "ndbi":
        swir = image.select("B11")
        nir = image.select("B8")
        return swir.subtract(nir).divide(swir.add(nir)).rename("index")
    raise ValueError(f"Unsupported index for Earth Engine catalog path: {index_name}")


def compute_index_change_magnitude(
    before: Any,
    after: Any,
    index_name: str,
    ee: Any,
) -> tuple[Any, Any]:
    """
    Return (absolute_index_diff, signed_index_diff) with combined valid mask.

    Signed diff = after_index - before_index (T2 minus T1).
    """
    before_idx = compute_index(before, index_name, ee)
    after_idx = compute_index(after, index_name, ee)
    combined_mask = before_idx.mask().And(after_idx.mask())
    b = before_idx.updateMask(combined_mask)
    a = after_idx.updateMask(combined_mask)
    signed = a.subtract(b).rename("signed_index_diff")
    magnitude = signed.abs().rename("change_magnitude")
    return magnitude, signed


def classify_direction_hint_from_median(median_delta: float, primary_index: str) -> str:
    """Heuristic direction hint from AOI-level signed index median (matches upload path)."""
    threshold = 0.02
    if abs(median_delta) < threshold:
        return "no_change"
    idx = primary_index.lower()
    if idx == "ndvi":
        return "vegetation_gain" if median_delta > 0 else "vegetation_loss"
    if idx == "ndwi":
        return "water_expansion" if median_delta > 0 else "water_contraction"
    if idx == "ndbi":
        return "built_up_increase" if median_delta > 0 else "built_up_decrease"
    return "index_increase" if median_delta > 0 else "index_decrease"
