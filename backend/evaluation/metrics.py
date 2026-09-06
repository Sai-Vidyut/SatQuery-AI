"""Region-level evaluation metrics (Phase 6)."""

from __future__ import annotations

from typing import Iterable

from shapely.geometry import shape
from shapely.ops import unary_union

from evaluation.models import QuantitativeMetrics
from app.schemas.domain import EvidenceRegion, GeoJSONGeometry


def _geometry_from_geojson(geom: GeoJSONGeometry):
    return shape(geom.model_dump())


def _regions_union(regions: Iterable[EvidenceRegion]):
    if not regions:
        return None
    shapes = [_geometry_from_geojson(r.geometry) for r in regions]
    return unary_union(shapes)


def compute_region_metrics(
    predicted_regions: list[EvidenceRegion],
    ground_truth_geometry: GeoJSONGeometry,
) -> QuantitativeMetrics:
    """
    Compute IoU / precision / recall / F1 between predicted region union
    and a single ground-truth polygon (same CRS — WGS84 expected).
    """
    pred_union = _regions_union(predicted_regions)
    gt_geom = _geometry_from_geojson(ground_truth_geometry)
    if pred_union is None or pred_union.is_empty:
        return QuantitativeMetrics(
            iou=0.0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            predicted_area_m2=0.0,
            ground_truth_area_m2=_approx_area_m2(gt_geom),
            changed_area_error_m2=_approx_area_m2(gt_geom),
            region_count_error=len(predicted_regions),
        )

    intersection = pred_union.intersection(gt_geom)
    union = pred_union.union(gt_geom)
    pred_area = _approx_area_m2(pred_union)
    gt_area = _approx_area_m2(gt_geom)
    inter_area = _approx_area_m2(intersection)
    union_area = _approx_area_m2(union)

    iou = inter_area / union_area if union_area > 0 else 0.0
    precision = inter_area / pred_area if pred_area > 0 else 0.0
    recall = inter_area / gt_area if gt_area > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return QuantitativeMetrics(
        iou=round(iou, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        predicted_area_m2=round(pred_area, 2),
        ground_truth_area_m2=round(gt_area, 2),
        changed_area_error_m2=round(abs(pred_area - gt_area), 2),
        region_count_error=len(predicted_regions),
    )


def _approx_area_m2(geom) -> float:
    """Planar degree-to-meter approximation at geometry centroid latitude."""
    if geom is None or geom.is_empty:
        return 0.0
    import math

    centroid = geom.centroid
    lat = centroid.y
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
    return float(abs(geom.area) * meters_per_deg_lat * meters_per_deg_lon)
