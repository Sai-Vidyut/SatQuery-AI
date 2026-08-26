#!/usr/bin/env python3
"""REAL SENTINEL-2 SMOKE TEST image fetch — NOT BigEarthNet adaptation.

Fetches one real Sentinel-2 L2A scene via the existing authenticated Earth
Engine workflow (same provider/policy SatQuery's production
EarthEngineProvider already uses), applies the documented RGB preprocessing
(preprocessing.py), and writes:
  - <out-dir>/sentinel2_smoketest.png       (504x504 visual RGB input for GeoChat)
  - <out-dir>/sentinel2_smoketest.metadata.json  (preserved geospatial metadata)

Requires:
  - `earthengine-api` installed (pip install -e ".[earth_engine]")
  - Earth Engine credentials already configured (reuses the same
    GOOGLE_APPLICATION_CREDENTIALS / EARTH_ENGINE_PROJECT env vars as the
    production backend; see backend/.env.example). This script does NOT
    read backend/.env directly (isolation) — pass --project explicitly or
    export EARTH_ENGINE_PROJECT yourself before running.

This label matters: any output file, log line, or downstream prediction
record produced from this image MUST be tagged
dataset="real_sentinel2_smoketest", never "bigearthnet_txt".
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phase9b.preprocessing import SceneMetadata  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=os.environ.get("EARTH_ENGINE_PROJECT"))
    parser.add_argument("--center-lon", type=float, default=16.60)
    parser.add_argument("--center-lat", type=float, default=48.20)
    parser.add_argument("--half-width-m", type=float, default=4000.0)
    parser.add_argument("--start-date", default="2023-06-01")
    parser.add_argument("--end-date", default="2023-09-01")
    parser.add_argument("--cloud-cover-max", type=float, default=5.0)
    parser.add_argument("--out-dir", type=Path, default=Path("data/real_sentinel2_smoketest"))
    args = parser.parse_args()

    if not args.project:
        print(
            "ERROR: no Earth Engine project configured. Pass --project or "
            "export EARTH_ENGINE_PROJECT.",
            file=sys.stderr,
        )
        return 1

    import ee

    ee.Initialize(project=args.project)

    dlat = args.half_width_m / 111_320
    dlon = args.half_width_m / (111_320 * math.cos(math.radians(args.center_lat)))
    aoi = ee.Geometry.Rectangle(
        [
            args.center_lon - dlon,
            args.center_lat - dlat,
            args.center_lon + dlon,
            args.center_lat + dlat,
        ]
    )

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(args.start_date, args.end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", args.cloud_cover_max))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )
    image = collection.first()
    info = image.getInfo()
    if info is None:
        print("ERROR: no Sentinel-2 scene matched the given AOI/date/cloud filter.", file=sys.stderr)
        return 1

    scene_id = info["properties"].get("PRODUCT_ID", info["id"])
    ts_ms = info["properties"].get("system:time_start")
    acquisition_iso = (
        datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat() if ts_ms else None
    )

    rgb = image.select(["B4", "B3", "B2"])
    url = rgb.getThumbURL(
        {
            "min": 0,
            "max": 3000,
            "dimensions": "504x504",
            "region": aoi,
            "format": "png",
        }
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    image_path = args.out_dir / "sentinel2_smoketest.png"
    urllib.request.urlretrieve(url, image_path)

    bounds = (
        args.center_lon - dlon,
        args.center_lat - dlat,
        args.center_lon + dlon,
        args.center_lat + dlat,
    )
    metadata = SceneMetadata(
        source="COPERNICUS/S2_SR_HARMONIZED (Google Earth Engine)",
        scene_id=scene_id,
        acquisition_time_iso=acquisition_iso,
        bounds_wgs84=bounds,
        crs="EPSG:4326",
        bands_used=("B04", "B03", "B02"),
        reflectance_stretch=(0, 3000),
    )
    metadata_path = args.out_dir / "sentinel2_smoketest.metadata.json"
    meta_dict = metadata.to_dict()
    meta_dict["label"] = "REAL_SENTINEL2_SMOKETEST"
    meta_dict["note"] = "This is NOT a BigEarthNet.txt example. See scripts/fetch_sentinel2_sample.py."
    metadata_path.write_text(json.dumps(meta_dict, indent=2))

    print(json.dumps(meta_dict, indent=2))
    print(f"\n[fetch] wrote {image_path} and {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
