"""Constants for Earth Engine Sentinel-1 SAR change detection."""

DETECTOR_VERSION = "1.1.0"
DETECTOR_NAME = "earth_engine_sar"

SAR_COLLECTION = "COPERNICUS/S1_GRD"
SAR_POLARIZATIONS = ("VV", "VH")
PRIMARY_POLARIZATION = "VV"

# Speckle filter: 3x3 focal median in linear backscatter domain.
SPECKLE_KERNEL_RADIUS_PX = 1
SPECKLE_KERNEL_TYPE = "square"

# Valid sigma0 range in linear units (~ -40 dB to 0 dB for Sentinel-1 GRD).
MIN_VALID_LINEAR_BACKSCATTER = 1e-4
MAX_VALID_LINEAR_BACKSCATTER = 1.0

# Reject per-pixel |delta dB| above this as mask-edge / near-zero artifacts.
MAX_PLAUSIBLE_CHANGE_DB = 25.0

# Absolute backscatter difference threshold in decibels (dB).
SAR_CHANGE_THRESHOLD_DB = 2.0

# Confidence is driven by this percentile of per-pixel change within each region.
SAR_CONFIDENCE_PERCENTILE = 90
SAR_CONFIDENCE_REFERENCE_DB = 15.0

MIN_REGION_AREA_M2 = 1500.0
ANALYSIS_SCALE_M = 10.0
VECTORIZATION_SCALE_M = 20.0
# SAR backscatter change is speckled; use a lower connected-pixel gate than optical CVA.
MIN_CONNECTED_PIXELS = 5
MAX_CHANGE_REGIONS = 50

# Detection policy v1.1.0 (documented):
# 1. Load before/after Sentinel-1 GRD scenes by platform_id from imagery pipeline.
# 2. Select VV and VH bands; require both polarizations in scene metadata.
# 3. Preserve the source image mask through speckle filtering.
# 4. Apply 3x3 focal median speckle filter in linear backscatter domain.
# 5. Mask pixels outside valid sigma0 range [1e-4, 1.0] linear (~ -40 dB to 0 dB).
# 6. Convert valid masked bands to dB: 10 * log10(linear) — no sub-floor clamping.
# 7. Compute per-pixel max(|VV_after - VV_before|, |VH_after - VH_before|) in dB.
# 8. Mask pixels with |delta| > MAX_PLAUSIBLE_CHANGE_DB (25 dB) as non-physical artifacts.
# 9. Threshold at SAR_CHANGE_THRESHOLD_DB (2.0 dB).
# 10. Vectorize connected components at VECTORIZATION_SCALE_M (20 m).
# 11. Require MIN_CONNECTED_PIXELS (5) at vectorization scale — lower than optical CVA
#     because speckle-filtered SAR change is naturally more fragmented.
# 12. Filter polygons below MIN_REGION_AREA_M2 (1500 m²); keep top MAX_CHANGE_REGIONS by area.
# 13. Per-region stats: mean, max, and p90 change magnitude over masked valid pixels.
# 14. Confidence = clamp((p90 - threshold) / (reference - threshold), 0, 1) with reference 15 dB.
# 15. Output SAR radar change evidence only — no semantic flood/construction/damage claims.
#
# Policy v1.0.0 differences (superseded):
# - Used 1e-10 linear floor (-100 dB), producing extreme dB deltas at mask edges.
# - Did not mask invalid backscatter or implausible per-pixel changes.
# - Confidence used mean magnitude with reference 6 dB (threshold * 3), saturating easily.

PROVENANCE_CHAIN = ["earth_engine_sar"]
