from __future__ import annotations

from typing import Any

from app.adapters.change.earth_engine.sar_constants import (
    MAX_PLAUSIBLE_CHANGE_DB,
    MAX_VALID_LINEAR_BACKSCATTER,
    MIN_VALID_LINEAR_BACKSCATTER,
    PRIMARY_POLARIZATION,
    SAR_POLARIZATIONS,
    SPECKLE_KERNEL_RADIUS_PX,
    SPECKLE_KERNEL_TYPE,
)


def load_sar_scene_image(ee: Any, platform_id: str) -> Any:
    return ee.Image(platform_id)


def _select_polarization_bands(image: Any, ee: Any) -> Any:
    """Select VV/VH bands present on the Sentinel-1 GRD image."""
    band_names = image.bandNames().getInfo()
    selected = [pol for pol in SAR_POLARIZATIONS if pol in band_names]
    if not selected:
        raise ValueError(f"Sentinel-1 scene missing required polarizations {SAR_POLARIZATIONS}")
    return image.select(selected)


def _apply_speckle_filter(band: Any, ee: Any) -> Any:
    """3x3 focal median in linear backscatter domain."""
    return band.focal_median(
        radius=SPECKLE_KERNEL_RADIUS_PX,
        kernelType=SPECKLE_KERNEL_TYPE,
        units="pixels",
    )


def _mask_valid_backscatter(band: Any, ee: Any) -> Any:
    """Keep only pixels within the physically plausible sigma0 range."""
    return (
        band.updateMask(band.gte(MIN_VALID_LINEAR_BACKSCATTER))
        .updateMask(band.lte(MAX_VALID_LINEAR_BACKSCATTER))
    )


def _linear_to_db(band: Any, ee: Any, polarization: str) -> Any:
    """Convert masked valid linear backscatter to decibels."""
    return band.log10().multiply(10).rename(f"{polarization}_db")


def prepare_sar_scene(image: Any, ee: Any) -> dict[str, Any]:
    """
    Prepare Sentinel-1 GRD scene: select polarizations, speckle filter, validity mask, dB.
    Returns dict mapping polarization -> dB image.
    """
    selected = _select_polarization_bands(image, ee)
    prepared: dict[str, Any] = {}
    for pol in SAR_POLARIZATIONS:
        if pol in selected.bandNames().getInfo():
            linear = selected.select(pol)
            original_mask = linear.mask()
            filtered = _apply_speckle_filter(linear, ee).updateMask(original_mask)
            valid = _mask_valid_backscatter(filtered, ee)
            prepared[pol] = _linear_to_db(valid, ee, pol)
    return prepared


def compute_sar_change_magnitude(
    before: dict[str, Any],
    after: dict[str, Any],
    ee: Any,
) -> Any:
    """
    Compute SAR change magnitude as max absolute dB difference across VV and VH.
    Masks implausible per-pixel deltas before vectorization/statistics.
    """
    diffs = []
    for pol in SAR_POLARIZATIONS:
        if pol not in before or pol not in after:
            continue
        combined_mask = before[pol].mask().And(after[pol].mask())
        diff = after[pol].subtract(before[pol]).abs().updateMask(combined_mask)
        plausible = diff.lte(MAX_PLAUSIBLE_CHANGE_DB)
        diff = diff.updateMask(plausible).rename("sar_change_db")
        diffs.append(diff)

    if not diffs:
        raise ValueError("Cannot compute SAR change magnitude without VV/VH polarizations")

    if len(diffs) == 1:
        return diffs[0].rename("sar_change_magnitude")

    collection = ee.ImageCollection(diffs)
    return collection.max().rename("sar_change_magnitude")


def polarization_summary(before: dict[str, Any], after: dict[str, Any]) -> dict[str, bool]:
    """Report which polarizations were used in the change computation."""
    return {
        pol: pol in before and pol in after
        for pol in SAR_POLARIZATIONS
    }


def primary_polarization_used(before: dict[str, Any], after: dict[str, Any]) -> str:
    if PRIMARY_POLARIZATION in before and PRIMARY_POLARIZATION in after:
        return PRIMARY_POLARIZATION
    for pol in SAR_POLARIZATIONS:
        if pol in before and pol in after:
            return pol
    return PRIMARY_POLARIZATION
