"""Catalog collection metadata for imagery policy decisions (Phase 5A).

No Earth Engine fetch logic — constants and helpers only.
"""

from __future__ import annotations

from datetime import date

# Sentinel-2 MSI (Copernicus)
SENTINEL2_COLLECTION_ID = "COPERNICUS/S2_SR_HARMONIZED"
SENTINEL2_OPERATIONAL_START = date(2015, 6, 23)
SENTINEL2_GSD_M = 10.0

# Landsat Collection 2 Level-2 (USGS) — representative GSD for policy
LANDSAT_COLLECTION_ID = "LANDSAT/LC08/C02/T1_L2"
LANDSAT_LE07_COLLECTION_ID = "LANDSAT/LE07/C02/T1_L2"
LANDSAT_GSD_M = 30.0
LANDSAT_PANCHROMATIC_GSD_M = 15.0
LANDSAT_AVAILABILITY_START = date(1999, 1, 1)

# NAIP (USDA) — CONUS aerial
NAIP_COLLECTION_ID = "USDA/NAIP/DOQQ"
NAIP_AVAILABILITY_START = date(2002, 6, 15)
NAIP_AVAILABILITY_END = date(2023, 11, 17)
NAIP_GSD_M_LEGACY = 1.0
NAIP_GSD_M_MODERN = 0.6
NAIP_MODERN_STANDARD_FROM = date(2018, 1, 1)

# Approximate CONUS bounding box [min_lon, min_lat, max_lon, max_lat]
NAIP_CONUS_BBOX: tuple[float, float, float, float] = (-125.0, 24.0, -66.0, 49.5)

# NAIP nominal acquisition epochs (year, month) used for policy date honesty.
# Real tile dates vary by state; catalog policy reports nearest epoch, not user year.
NAIP_NOMINAL_EPOCHS: tuple[tuple[int, int], ...] = (
    (2003, 7),
    (2004, 7),
    (2005, 7),
    (2006, 7),
    (2008, 7),
    (2009, 7),
    (2010, 7),
    (2011, 7),
    (2012, 7),
    (2013, 7),
    (2014, 7),
    (2015, 7),
    (2016, 7),
    (2017, 7),
    (2018, 7),
    (2019, 7),
    (2020, 7),
    (2021, 7),
    (2022, 7),
    (2023, 7),
)

BUILDING_INSTANCE_MAX_GSD_M = 2.0
MAX_GSD_MISMATCH_RATIO = 2.0


def bbox_intersects(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    """Return True when two lon/lat bboxes overlap."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def aoi_bbox_intersects_conus(bbox: list[float]) -> bool:
    if len(bbox) != 4:
        return False
    aoi = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    return bbox_intersects(aoi, NAIP_CONUS_BBOX)


def naip_gsd_for_date(acquisition: date) -> float:
    if acquisition >= NAIP_MODERN_STANDARD_FROM:
        return NAIP_GSD_M_MODERN
    return NAIP_GSD_M_LEGACY


def nearest_naip_epoch(requested: date) -> date:
    """Pick the closest nominal NAIP epoch; does not claim exact user-year match."""
    best = date(NAIP_NOMINAL_EPOCHS[0][0], NAIP_NOMINAL_EPOCHS[0][1], 1)
    best_delta = abs((requested - best).days)
    for year, month in NAIP_NOMINAL_EPOCHS:
        candidate = date(year, month, 1)
        delta = abs((requested - candidate).days)
        if delta < best_delta:
            best = candidate
            best_delta = delta
    return best


def naip_available_for_date(requested: date) -> bool:
    return NAIP_AVAILABILITY_START <= requested <= NAIP_AVAILABILITY_END


def sentinel2_available_for_date(requested: date) -> bool:
    return requested >= SENTINEL2_OPERATIONAL_START


def landsat_available_for_date(requested: date) -> bool:
    return requested >= LANDSAT_AVAILABILITY_START
