#!/usr/bin/env python3
"""Validate spatial output from live Earth Engine CVA detection."""
from __future__ import annotations

import json
import math
import sys
import urllib.request
from collections import Counter
from typing import Any

from app.adapters.change.earth_engine.constants import (
    CVA_CONFIDENCE_REFERENCE_MAGNITUDE,
    CVA_MAGNITUDE_THRESHOLD,
    MIN_REGION_AREA_M2,
)
AOI_RING = [
    [77.56, 12.94],
    [77.60, 12.94],
    [77.60, 12.98],
    [77.56, 12.98],
    [77.56, 12.94],
]
AOI_BBOX = (77.56, 12.94, 77.60, 12.98)  # min_lon, min_lat, max_lon, max_lat
CVA_THRESHOLD = CVA_MAGNITUDE_THRESHOLD
CVA_CONF_REF = CVA_CONFIDENCE_REFERENCE_MAGNITUDE

QUERY_PAYLOAD = {
    "query": "Detect significant spectral change in this area between December 2024 and March 2025.",
    "aoi": {"geometry": {"type": "Polygon", "coordinates": [AOI_RING]}},
    "earlier_date": "2024-12-01",
    "later_date": "2025-03-01",
    "sensor": "sentinel-2",
    "preferences": {"cloud_cover_max": 30},
}


def polygon_area_m2(ring: list[list[float]]) -> float:
    coords = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    if len(coords) < 3:
        return 0.0
    mean_lat = sum(p[1] for p in coords) / len(coords)
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * math.cos(math.radians(mean_lat))
    area = 0.0
    for i in range(len(coords)):
        x1, y1 = coords[i][0] * lon_scale, coords[i][1] * lat_scale
        x2, y2 = coords[(i + 1) % len(coords)][0] * lon_scale, coords[(i + 1) % len(coords)][1] * lat_scale
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def point_in_polygon(x: float, y: float, polygon: list[list[float]]) -> bool:
    inside = False
    n = len(polygon) - 1 if polygon[0] == polygon[-1] else len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi):
            inside = not inside
        j = i
    return inside


def polygon_centroid(ring: list[list[float]]) -> tuple[float, float]:
    coords = ring[:-1] if ring[0] == ring[-1] else ring
    if not coords:
        return 0.0, 0.0
    return sum(p[0] for p in coords) / len(coords), sum(p[1] for p in coords) / len(coords)


def bbox_of_ring(ring: list[list[float]]) -> tuple[float, float, float, float]:
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return min(lons), min(lats), max(lons), max(lats)


def bboxes_touch_or_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    buffer: float = 0.00005,
) -> bool:
    return not (
        a[2] + buffer < b[0]
        or b[2] + buffer < a[0]
        or a[3] + buffer < b[1]
        or b[3] + buffer < a[1]
    )


def fetch_live_result(base_url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{base_url}/api/v1/query/submit",
        data=json.dumps(QUERY_PAYLOAD).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        body = json.loads(resp.read().decode())
    if not body.get("success"):
        raise RuntimeError(body)
    return body["data"]["result"]


def metric_value(region: dict, name: str) -> float | None:
    for m in region.get("metrics", []):
        if m["name"] == name:
            return float(m["value"])
    return None


def expected_confidence(mean_mag: float) -> float:
    if mean_mag <= CVA_THRESHOLD:
        return 0.0
    return round(min(1.0, (mean_mag - CVA_THRESHOLD) / (CVA_CONF_REF - CVA_THRESHOLD)), 3)


def validate_regions(result: dict[str, Any]) -> dict[str, Any]:
    regions = result.get("evidence", [])
    issues: list[str] = []
    areas_m2: list[float] = []
    confidences: list[float] = []
    bboxes: list[tuple[float, float, float, float]] = []
    vertex_counts: list[int] = []

    aoi_area_m2 = polygon_area_m2(AOI_RING)
    seeded_rect_signatures = 0

    for i, region in enumerate(regions):
        rid = region.get("id", f"region-{i}")
        geom = region.get("geometry", {})
        gtype = geom.get("type")
        coords = geom.get("coordinates")

        # 1. Valid GeoJSON
        if gtype != "Polygon":
            issues.append(f"{rid}: invalid geometry type {gtype}")
            continue
        if not coords or not isinstance(coords, list) or not coords[0]:
            issues.append(f"{rid}: empty coordinates")
            continue
        ring = coords[0]
        if len(ring) < 4:
            issues.append(f"{rid}: ring has < 4 points")
            continue
        if ring[0] != ring[-1]:
            issues.append(f"{rid}: ring not closed")
        for pt in ring:
            if not isinstance(pt, list) or len(pt) < 2:
                issues.append(f"{rid}: invalid coordinate {pt}")
                continue
            lon, lat = float(pt[0]), float(pt[1])
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                issues.append(f"{rid}: out-of-range coordinate ({lon}, {lat})")

        area_m2 = polygon_area_m2(ring)
        areas_m2.append(area_m2)
        vertex_counts.append(len(ring))
        bboxes.append(bbox_of_ring(ring))

        # 3. Non-zero area
        if area_m2 <= 0:
            issues.append(f"{rid}: zero/negative area {area_m2}")

        # 2. Within AOI (centroid + all vertices)
        cx, cy = polygon_centroid(ring)
        if not point_in_polygon(cx, cy, AOI_RING):
            issues.append(f"{rid}: centroid outside AOI ({cx:.5f}, {cy:.5f})")
        for pt in ring:
            if not point_in_polygon(pt[0], pt[1], AOI_RING):
                issues.append(f"{rid}: vertex ({pt[0]}, {pt[1]}) outside AOI")
                break

        # 4. Metrics correspond to geometry
        area_km2_metric = metric_value(region, "area_km2")
        if area_km2_metric is None:
            issues.append(f"{rid}: missing area_km2 metric")
        else:
            computed_km2 = area_m2 / 1_000_000.0
            rel_err = abs(area_km2_metric - computed_km2) / max(computed_km2, 1e-9)
            if rel_err > 0.05:
                issues.append(
                    f"{rid}: area_km2 mismatch metric={area_km2_metric:.6f} geom={computed_km2:.6f}"
                )

        mean_mag = metric_value(region, "mean_change_magnitude")
        max_mag = metric_value(region, "max_change_magnitude")
        if mean_mag is None or max_mag is None:
            issues.append(f"{rid}: missing magnitude metrics")
        elif max_mag < mean_mag:
            issues.append(f"{rid}: max < mean ({max_mag} < {mean_mag})")
        elif mean_mag < CVA_THRESHOLD and region.get("confidence", 0) > 0:
            issues.append(f"{rid}: confidence > 0 but mean below threshold")

        conf = float(region.get("confidence", 0))
        confidences.append(conf)
        if mean_mag is not None:
            exp = expected_confidence(mean_mag)
            if abs(conf - exp) > 0.001:
                issues.append(f"{rid}: confidence {conf} != expected {exp}")

        # 5. Not seeded detector patterns
        if region.get("type") == "construction_change":
            issues.append(f"{rid}: seeded detector type construction_change")
        if region.get("source") != "earth_engine_cva":
            issues.append(f"{rid}: unexpected source {region.get('source')}")
        if len(ring) == 5 and area_m2 > 0:
            # seeded detector uses 4-corner rectangles with 5 points
            lons = sorted({round(p[0], 6) for p in ring})
            lats = sorted({round(p[1], 6) for p in ring})
            if len(lons) == 2 and len(lats) == 2:
                seeded_rect_signatures += 1

    # Adjacency / fragmentation heuristic
    adjacent_pairs = 0
    for i in range(len(bboxes)):
        for j in range(i + 1, len(bboxes)):
            if bboxes_touch_or_overlap(bboxes[i], bboxes[j]):
                adjacent_pairs += 1

    small_regions = sum(1 for a in areas_m2 if a < 5_000)  # < 0.005 km²
    tiny_regions = sum(1 for a in areas_m2 if a < MIN_REGION_AREA_M2 * 1.5)
    high_vertex = sum(1 for v in vertex_counts if v > 50)

    total_changed_m2 = sum(areas_m2)
    pct_aoi = (total_changed_m2 / aoi_area_m2 * 100) if aoi_area_m2 else 0

    conf_hist = Counter()
    for c in confidences:
        bucket = f"{int(c * 10) * 10}-{int(c * 10) * 10 + 9}%"
        conf_hist[bucket] += 1

    return {
        "region_count": len(regions),
        "aoi_area_km2": round(aoi_area_m2 / 1_000_000, 4),
        "total_changed_area_km2": round(total_changed_m2 / 1_000_000, 4),
        "pct_aoi_affected": round(pct_aoi, 2),
        "smallest_region_km2": round(min(areas_m2) / 1_000_000, 6) if areas_m2 else 0,
        "largest_region_km2": round(max(areas_m2) / 1_000_000, 6) if areas_m2 else 0,
        "mean_region_area_km2": round((sum(areas_m2) / len(areas_m2)) / 1_000_000, 6) if areas_m2 else 0,
        "mean_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
        "confidence_distribution": dict(sorted(conf_hist.items())),
        "mode": result.get("mode"),
        "detector": next((m["value"] for m in result.get("metrics", []) if m["name"] == "detector"), None),
        "issues": issues,
        "fragmentation": {
            "regions_under_0_005_km2": small_regions,
            "regions_under_min_filter_x1_5": tiny_regions,
            "regions_with_gt_50_vertices": high_vertex,
            "adjacent_bbox_pairs": adjacent_pairs,
            "seeded_rect_signatures": seeded_rect_signatures,
            "mean_vertices": round(sum(vertex_counts) / len(vertex_counts), 1) if vertex_counts else 0,
            "median_vertices": sorted(vertex_counts)[len(vertex_counts) // 2] if vertex_counts else 0,
        },
        "trace": [
            {"tool": t["tool_name"], "status": t["status"], "ms": t.get("duration_ms")}
            for t in result.get("trace", [])
        ],
    }


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8002"
    use_cache = "--cache" in sys.argv
    if use_cache:
        with open("/tmp/satquery_e2e_result.json") as f:
            cached = json.load(f)
        result = cached["response"]["data"]["result"]
        source = "cache"
    else:
        result = fetch_live_result(base_url)
        source = base_url

    report = validate_regions(result)
    report["data_source"] = source
    print(json.dumps(report, indent=2))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
