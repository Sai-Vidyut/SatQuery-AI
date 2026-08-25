"""Constants for Earth Engine Sentinel-2 change vector analysis."""

DETECTOR_VERSION = "1.1.0"

# Spectral bands used for change vector magnitude (surface reflectance scale 0–10000).
CVA_BANDS: list[str] = ["B2", "B3", "B4", "B8", "B11", "B12"]

# Magnitude threshold on Euclidean distance in spectral space (SR scale).
# Policy v1.1.0: raised from 800 to reduce mixed-pixel false positives.
CVA_MAGNITUDE_THRESHOLD = 1000.0

# Reference magnitude for normalizing confidence (3× threshold).
CVA_CONFIDENCE_REFERENCE_MAGNITUDE = CVA_MAGNITUDE_THRESHOLD * 3.0

# Minimum connected-component area to keep (m²).
MIN_REGION_AREA_M2 = 2000.0

# Analysis scale (Sentinel-2 native 10 m bands).
ANALYSIS_SCALE_M = 10.0

# Coarser scale for vectorization to limit polygon fragmentation.
VECTORIZATION_SCALE_M = 20.0

# Minimum connected pixels at vectorization scale before polygon extraction.
MIN_CONNECTED_PIXELS = 100

# Cap vectorized regions returned per request.
MAX_CHANGE_REGIONS = 50

# Detection policy v1.1.0 (documented):
# 1. Load before/after scenes by platform_id from imagery pipeline.
# 2. Apply QA60 + SCL cloud/shadow masking on both scenes.
# 3. Select CVA_BANDS and compute Euclidean change magnitude.
# 4. Threshold at CVA_MAGNITUDE_THRESHOLD (1000).
# 5. Vectorize connected components at VECTORIZATION_SCALE_M (20 m).
# 6. Filter polygons below MIN_REGION_AREA_M2 (2000 m²); keep top MAX_CHANGE_REGIONS by area.
# 7. Clip vectors to AOI; confidence = clamp((mean_magnitude - threshold) / (reference - threshold), 0, 1).
