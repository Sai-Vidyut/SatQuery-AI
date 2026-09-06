"""Shared constants for Earth Engine imagery adapters."""

SENTINEL2_SR_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
SENTINEL2_RESOLUTION_M = 10.0

SENTINEL1_GRD_COLLECTION = "COPERNICUS/S1_GRD"
SENTINEL1_RESOLUTION_M = 10.0
SENTINEL1_POLARIZATIONS = ("VV", "VH")
SENTINEL1_INSTRUMENT_MODE = "IW"

# Selection policy version — bump when policy changes.
SELECTION_POLICY_VERSION = "1.1.0"
SENTINEL1_SELECTION_POLICY_VERSION = "1.0.0"

# Sentinel-2 selection policy v1.1.0 (documented):
# 1. Filter collection to AOI bounds and [start_date, end_date].
# 2. Filter CLOUDY_PIXEL_PERCENTAGE < cloud_cover_max from preferences.
# 3. If no scenes remain → error.
# 4. Select start_anchor scene: prefer same-season month (seasonal_selection_penalty),
#    then minimize |acquisition_date - start_date|, tie-break lower cloud,
#    then lexicographic system:index.
# 5. Select end_anchor scene: same rule vs end_date.
# 6. Return unique scenes in chronological order.
# 7. Seasonality provenance (cross-season warning, date offsets) attached at provider.

# Sentinel-1 selection policy v1.0.0 (documented):
# 1. Filter COPERNICUS/S1_GRD to AOI bounds and [start_date, end_date].
# 2. Require instrumentMode=IW and VV+VH polarizations.
# 3. Group scenes by relativeOrbitNumber.
# 4. Pick orbit group with scenes on both sides of the date-range midpoint
#    (tie-break: most scenes, then lowest orbit number).
# 5. Select start_anchor / end_anchor within that orbit using the same
#    distance-to-target-date rule as Sentinel-2 (tie: scene_id).
# 6. Return unique scenes in chronological order.
