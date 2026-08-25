"""Constants for Earth Engine Dynamic World semantic analyzer."""

POLICY_NAME = "dynamic_world_built_construction_v1"
POLICY_VERSION = "1.0.0"

DYNAMIC_WORLD_COLLECTION = "GOOGLE/DYNAMICWORLD/V1"
BUILT_BAND = "built"

DELTA_BUILT_THRESHOLD = 0.15
CVA_OVERLAP_THRESHOLD = 0.30
MIN_REGION_AREA_M2 = 2000.0
CONFIDENCE_SCALE = 0.40

ANALYSIS_SCALE_M = 10.0

# Temporal window policy v1.0.0 — anchored to Sentinel-2 scene acquisition dates.
TEMPORAL_WINDOW_POLICY = "1.0.0"
WINDOW_DAYS_BEFORE = 0
WINDOW_DAYS_AFTER = 7

ANALYZER_NAME = "dynamic_world_built_v1"
PROVENANCE_CHAIN = ["earth_engine_cva", "dynamic_world_built_v1"]
