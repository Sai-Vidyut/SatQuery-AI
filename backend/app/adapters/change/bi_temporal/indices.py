"""Spectral index computation for uploaded optical/SAR rasters."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_EPS = 1e-10

# Sentinel-2-like default band roles (0-indexed) when band_names are absent.
_DEFAULT_OPTICAL_BANDS: dict[str, int] = {
    "blue": 0,
    "green": 1,
    "red": 2,
    "nir": 3,
    "swir": 4,
}
_DEFAULT_SAR_BANDS: dict[str, int] = {"vv": 0, "vh": 1}

_SENTINEL2_NAME_MAP: dict[str, str] = {
    "b2": "blue",
    "blue": "blue",
    "b3": "green",
    "green": "green",
    "b4": "red",
    "red": "red",
    "b8": "nir",
    "nir": "nir",
    "b11": "swir",
    "b12": "swir",
    "swir": "swir",
    "vv": "vv",
    "vh": "vh",
}

_INDEX_MIN_BANDS: dict[str, int] = {
    "ndvi": 4,
    "ndwi": 4,
    "ndbi": 5,
    "rvi": 2,
    "band_1": 1,
}

_QUERY_HINT_MAP: dict[str, str] = {
    "vegetation": "ndvi",
    "forest": "ndvi",
    "crop": "ndvi",
    "green": "ndvi",
    "ndvi": "ndvi",
    "deforest": "ndvi",
    "water": "ndwi",
    "flood": "ndwi",
    "river": "ndwi",
    "lake": "ndwi",
    "ndwi": "ndwi",
    "wetland": "ndwi",
    "urban": "ndbi",
    "built": "ndbi",
    "building": "ndbi",
    "city": "ndbi",
    "ndbi": "ndbi",
    "road": "ndbi",
    "sar": "rvi",
    "backscatter": "rvi",
    "rvi": "rvi",
}

_INDEX_PRIORITY_OPTICAL = ["ndvi", "ndwi", "ndbi"]
_INDEX_PRIORITY_SAR = ["rvi"]


def _norm_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    num = a.astype(np.float32) - b.astype(np.float32)
    den = a.astype(np.float32) + b.astype(np.float32)
    return np.where(np.abs(den) < _EPS, 0.0, num / den).astype(np.float32)


def ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    return _norm_diff(nir, red)


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    return _norm_diff(green, nir)


def ndbi(swir: np.ndarray, nir: np.ndarray) -> np.ndarray:
    return _norm_diff(swir, nir)


def rvi(vv: np.ndarray, vh: np.ndarray) -> np.ndarray:
    num = 4.0 * vh.astype(np.float32)
    den = vv.astype(np.float32) + vh.astype(np.float32)
    return np.where(np.abs(den) < _EPS, 0.0, num / den).astype(np.float32)


_INDEX_PRIORITY_OPTICAL = ["ndvi", "ndwi", "ndbi"]
_INDEX_PRIORITY_SAR = ["rvi"]


@dataclass(frozen=True)
class BandMapSelection:
    band_map: dict[str, int]
    positional_fallback_used: bool
    mapping_source: str


def build_band_map(
    band_names: list[str] | None,
    band_count: int,
    *,
    modality: str = "optical",
) -> dict[str, int]:
    """Return role→band-index mapping (backward-compatible helper)."""
    return build_band_map_selection(band_names, band_count, modality=modality).band_map


def build_band_map_selection(
    band_names: list[str] | None,
    band_count: int,
    *,
    modality: str = "optical",
) -> BandMapSelection:
    """Map spectral roles to band indices from ImageInput.band_names or defaults."""
    if band_names:
        role_map: dict[str, int] = {}
        for idx, raw in enumerate(band_names):
            key = _SENTINEL2_NAME_MAP.get(raw.lower().strip(), raw.lower().strip())
            if key not in role_map:
                role_map[key] = idx
        has_spectral_roles = any(r in role_map for r in ("red", "nir", "green", "swir", "vv", "vh"))
        if not has_spectral_roles:
            if modality == "sar" and band_count >= 2:
                return BandMapSelection(
                    band_map={role: idx for role, idx in _DEFAULT_SAR_BANDS.items() if idx < band_count},
                    positional_fallback_used=True,
                    mapping_source="default_sar_layout",
                )
            if band_count >= 4:
                return BandMapSelection(
                    band_map={role: idx for role, idx in _DEFAULT_OPTICAL_BANDS.items() if idx < band_count},
                    positional_fallback_used=True,
                    mapping_source="default_optical_layout",
                )
        return BandMapSelection(
            band_map=role_map,
            positional_fallback_used=False,
            mapping_source="band_names",
        )

    if modality == "sar" and band_count >= 2:
        return BandMapSelection(
            band_map=dict(_DEFAULT_SAR_BANDS),
            positional_fallback_used=True,
            mapping_source="default_sar_layout",
        )
    if band_count >= 4:
        return BandMapSelection(
            band_map={role: idx for role, idx in _DEFAULT_OPTICAL_BANDS.items() if idx < band_count},
            positional_fallback_used=True,
            mapping_source="default_optical_layout",
        )
    return BandMapSelection(band_map={}, positional_fallback_used=False, mapping_source="insufficient_bands")


def available_indices(
    band_count: int,
    band_map: dict[str, int],
    *,
    modality: str = "optical",
) -> list[str]:
    if modality == "sar":
        if "vv" in band_map and "vh" in band_map:
            return ["rvi"]
        return ["band_1"] if band_count >= 1 else []

    candidates = ["ndvi", "ndwi", "ndbi"]
    available: list[str] = []
    for idx_name in candidates:
        if band_count < _INDEX_MIN_BANDS[idx_name]:
            continue
        if idx_name == "ndvi" and "red" in band_map and "nir" in band_map:
            available.append(idx_name)
        elif idx_name == "ndwi" and "green" in band_map and "nir" in band_map:
            available.append(idx_name)
        elif idx_name == "ndbi" and "swir" in band_map and "nir" in band_map:
            available.append(idx_name)
    if not available and band_count >= 1:
        return ["band_1"]
    return available


def select_primary_index(
    band_count: int,
    band_map: dict[str, int],
    *,
    modality: str = "optical",
    query_hint: str = "",
) -> str:
    avail = available_indices(band_count, band_map, modality=modality)
    hint = query_hint.lower()
    for keyword, index in _QUERY_HINT_MAP.items():
        if keyword in hint and index in avail:
            return index

    priority = _INDEX_PRIORITY_SAR if modality == "sar" else _INDEX_PRIORITY_OPTICAL
    for index in priority:
        if index in avail:
            return index
    return avail[0] if avail else "band_1"


def extract_index(
    array: np.ndarray,
    index_name: str,
    band_map: dict[str, int],
) -> np.ndarray | None:
    """Compute a named index from a (B, H, W) float32 array."""
    n_bands = array.shape[0]

    def _get(role: str) -> np.ndarray | None:
        idx = band_map.get(role)
        if idx is None or idx >= n_bands:
            return None
        return array[idx]

    name = index_name.lower()
    if name == "ndvi":
        red, nir_band = _get("red"), _get("nir")
        return ndvi(red, nir_band) if red is not None and nir_band is not None else None
    if name == "ndwi":
        green, nir_band = _get("green"), _get("nir")
        return ndwi(green, nir_band) if green is not None and nir_band is not None else None
    if name == "ndbi":
        swir, nir_band = _get("swir"), _get("nir")
        return ndbi(swir, nir_band) if swir is not None and nir_band is not None else None
    if name == "rvi":
        vv, vh = _get("vv"), _get("vh")
        return rvi(vv, vh) if vv is not None and vh is not None else None
    if name == "band_1" and n_bands >= 1:
        return array[0].astype(np.float32)
    return None
