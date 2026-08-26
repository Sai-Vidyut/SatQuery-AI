"""
PHASE 9A SMOKE TEST — TEMPORARY SCRIPT (not part of SatQuery-AI application).

Fetches ONE real Sentinel-2 L2A RGB thumbnail via Earth Engine using the
already-authenticated `earthengine authenticate` credentials on this machine.
Uses B04/B03/B02 (Red/Green/Blue) per documented Sentinel-2 band mapping,
matching the same convention BigEarthNet.txt's own loader uses for RGB.

This does NOT touch backend/app/adapters/* — it is a standalone read-only
Earth Engine call for smoke-test purposes only.
"""
import json
import pathlib

import ee

PROJECT_ID = pathlib.Path("/tmp/ee_project.txt").read_text().strip()
ee.Initialize(project=PROJECT_ID)

# A cloud-free, visually unambiguous AOI: mixed urban/agricultural area near
# Vienna, Austria (one of the 10 BigEarthNet source countries) so the scene
# is representative of the same land-cover domain GeoChat/BigEarthNet target.
# Longitude delta compensated by cos(latitude) so the region is square in meters
# (not just in degrees), avoiding letterboxing in the square thumbnail.
import math

CENTER_LON, CENTER_LAT = 16.60, 48.20
HALF_WIDTH_M = 4000  # 8km x 8km AOI
dlat = HALF_WIDTH_M / 111_320
dlon = HALF_WIDTH_M / (111_320 * math.cos(math.radians(CENTER_LAT)))
AOI = ee.Geometry.Rectangle([
    CENTER_LON - dlon, CENTER_LAT - dlat,
    CENTER_LON + dlon, CENTER_LAT + dlat,
])

collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(AOI)
    .filterDate("2023-06-01", "2023-09-01")
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 5))
    .sort("CLOUDY_PIXEL_PERCENTAGE")
)

image = collection.first()
info = image.getInfo()
scene_id = info["properties"].get("PRODUCT_ID", info["id"])
acquisition = info["properties"].get("system:time_start")

rgb = image.select(["B4", "B3", "B2"])

# Documented Sentinel-2 L2A reflectance scaling: raw DN / 10000 = surface reflectance [0,1].
# For an 8-bit RGB preview we stretch reflectance [0, 0.3] -> [0, 255], the standard
# "true color" visualization range used by Copernicus/EE for Sentinel-2 L2A previews.
url = rgb.getThumbURL({
    "min": 0,
    "max": 3000,
    "dimensions": "504x504",  # match GeoChat's native 504x504 CLIP input resolution
    "region": AOI,
    "format": "png",
})

out = pathlib.Path(__file__).parent / "smoketest_image.png"
import urllib.request
urllib.request.urlretrieve(url, out)

meta = {
    "source": "COPERNICUS/S2_SR_HARMONIZED (Google Earth Engine)",
    "scene_id": scene_id,
    "acquisition_time_start_ms": acquisition,
    "bands": ["B4 (Red)", "B3 (Green)", "B2 (Blue)"],
    "scaling": "surface reflectance DN, stretched [0, 3000] -> [0, 255] (standard true-color preview)",
    "aoi_wgs84": [CENTER_LON - dlon, CENTER_LAT - dlat, CENTER_LON + dlon, CENTER_LAT + dlat],
    "output_dimensions_px": 504,
    "output_file": str(out),
}
(pathlib.Path(__file__).parent / "smoketest_image_metadata.json").write_text(
    json.dumps(meta, indent=2)
)
print(json.dumps(meta, indent=2))
