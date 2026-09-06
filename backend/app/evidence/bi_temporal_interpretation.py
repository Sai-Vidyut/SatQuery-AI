"""Evidence-grounded interpretation helpers for uploaded bi-temporal change results."""

from __future__ import annotations

from typing import Any

from app.schemas.bi_temporal_change import (
    BiTemporalDetectorSummary,
    BiTemporalImageProvenance,
    BiTemporalSceneMetrics,
)
from app.schemas.domain import EvidenceRegion, Metric
from app.schemas.input import ImageInput

CONFIDENCE_KIND = "histogram_separability"

_DIRECTION_HINT_PHRASES: dict[str, str] = {
    "no_change": "no directional signal",
    "vegetation_loss": "vegetation loss",
    "vegetation_gain": "vegetation gain",
    "water_expansion": "water expansion",
    "water_contraction": "water contraction",
    "built_up_increase": "built-up increase",
    "built_up_decrease": "built-up decrease",
    "sar_backscatter_increase": "SAR backscatter increase",
    "sar_backscatter_decrease": "SAR backscatter decrease",
    "index_increase": "index increase",
    "index_decrease": "index decrease",
}

_INDEX_LABELS: dict[str, str] = {
    "ndvi": "NDVI",
    "ndwi": "NDWI",
    "ndbi": "NDBI",
    "rvi": "RVI",
    "band_1": "band 1",
}

_SCENE_METRIC_KEYS: tuple[tuple[str, str | None], ...] = (
    ("changed_pixel_count", "pixels"),
    ("total_pixel_count", "pixels"),
    ("changed_percentage", "%"),
    ("area_m2", "m²"),
    ("area_ha", "ha"),
    ("area_km2", "km²"),
    ("region_count", "regions"),
)


def humanize_direction_hint(hint: str | None) -> str:
    if not hint:
        return "no directional signal"
    return _DIRECTION_HINT_PHRASES.get(hint, hint.replace("_", " "))


def format_primary_index(index_name: str | None) -> str:
    if not index_name:
        return "spectral index"
    return _INDEX_LABELS.get(index_name.lower(), index_name.upper())


def extract_scene_metrics(detector_metadata: dict[str, Any]) -> BiTemporalSceneMetrics | None:
    if not detector_metadata:
        return None
    values = {key: detector_metadata.get(key) for key, _ in _SCENE_METRIC_KEYS}
    if not any(v is not None for v in values.values()):
        return None
    return BiTemporalSceneMetrics(
        changed_pixel_count=values["changed_pixel_count"],
        total_pixel_count=values["total_pixel_count"],
        changed_percentage=values["changed_percentage"],
        area_m2=values["area_m2"],
        area_ha=values["area_ha"],
        area_km2=values["area_km2"],
        region_count=values.get("region_count") or detector_metadata.get("region_count"),
    )


def extract_detector_summary(
    detector: str,
    detector_metadata: dict[str, Any],
    *,
    histogram_confidence: float | None,
) -> BiTemporalDetectorSummary | None:
    if not detector_metadata and not histogram_confidence:
        return BiTemporalDetectorSummary(detector=detector)
    return BiTemporalDetectorSummary(
        detector=detector,
        algorithm=detector_metadata.get("algorithm"),
        detector_version=detector_metadata.get("detector_version"),
        primary_index=detector_metadata.get("primary_index"),
        change_direction_hint=detector_metadata.get("change_direction_hint"),
        histogram_confidence=histogram_confidence,
        confidence_kind=detector_metadata.get("confidence_kind") or CONFIDENCE_KIND,
    )


def extract_image_provenance(
    detector_metadata: dict[str, Any],
    earlier: ImageInput,
    later: ImageInput,
) -> BiTemporalImageProvenance:
    inputs = detector_metadata.get("inputs") if detector_metadata else None
    inputs = inputs if isinstance(inputs, dict) else {}
    raster = detector_metadata.get("raster") if detector_metadata else None
    raster = raster if isinstance(raster, dict) else {}
    return BiTemporalImageProvenance(
        earlier_source_ref=inputs.get("earlier_source_ref") or f"upload://{earlier.id}",
        later_source_ref=inputs.get("later_source_ref") or f"upload://{later.id}",
        earlier_filename=inputs.get("earlier_filename") or earlier.filename,
        later_filename=inputs.get("later_filename") or later.filename,
        earlier_modality=inputs.get("earlier_modality") or earlier.modality.value,
        later_modality=inputs.get("later_modality") or later.modality.value,
        earlier_band_names=inputs.get("earlier_band_names") or earlier.band_names,
        later_band_names=inputs.get("later_band_names") or later.band_names,
        crs=detector_metadata.get("crs") or raster.get("crs") or earlier.crs,
        coregistration_performed=detector_metadata.get("coregistration_performed"),
        positional_band_fallback_used=detector_metadata.get("positional_band_fallback_used"),
    )


def compact_detector_provenance(detector_metadata: dict[str, Any]) -> dict[str, Any]:
    """Safe provenance bag for inference_metadata without local paths or raster payloads."""
    if not detector_metadata:
        return {}
    configuration = detector_metadata.get("configuration")
    return {
        "algorithm": detector_metadata.get("algorithm"),
        "detector_version": detector_metadata.get("detector_version"),
        "primary_index": detector_metadata.get("primary_index"),
        "change_direction_hint": detector_metadata.get("change_direction_hint"),
        "histogram_confidence": detector_metadata.get("histogram_confidence"),
        "confidence_kind": detector_metadata.get("confidence_kind") or CONFIDENCE_KIND,
        "changed_pixel_count": detector_metadata.get("changed_pixel_count"),
        "total_pixel_count": detector_metadata.get("total_pixel_count"),
        "changed_percentage": detector_metadata.get("changed_percentage"),
        "area_m2": detector_metadata.get("area_m2"),
        "area_ha": detector_metadata.get("area_ha"),
        "area_km2": detector_metadata.get("area_km2"),
        "region_count": detector_metadata.get("region_count"),
        "pipeline_stage_names": detector_metadata.get("pipeline_stage_names"),
        "inputs": detector_metadata.get("inputs"),
        "raster": detector_metadata.get("raster"),
        "crs": detector_metadata.get("crs"),
        "band_mapping": detector_metadata.get("band_mapping"),
        "mapping_source": detector_metadata.get("mapping_source"),
        "positional_band_fallback_used": detector_metadata.get("positional_band_fallback_used"),
        "coregistration_performed": detector_metadata.get("coregistration_performed"),
        "configuration": configuration if isinstance(configuration, dict) else None,
    }


def metrics_from_detector_metadata(
    detector_metadata: dict[str, Any],
    *,
    source: str,
) -> list[Metric]:
    if not detector_metadata:
        return []
    metrics: list[Metric] = []
    for key, unit in _SCENE_METRIC_KEYS:
        value = detector_metadata.get(key)
        if value is None:
            continue
        metrics.append(
            Metric(
                name=key,
                value=value,
                unit=unit,
                source=source,
            )
        )
    for key, unit in (
        ("histogram_confidence", "ratio"),
        ("primary_index", None),
        ("change_direction_hint", None),
    ):
        value = detector_metadata.get(key)
        if value is None:
            continue
        metrics.append(Metric(name=key, value=value, unit=unit, source=source))
    confidence_kind = detector_metadata.get("confidence_kind") or CONFIDENCE_KIND
    metrics.append(
        Metric(
            name="confidence_kind",
            value=confidence_kind,
            unit=None,
            source=source,
        )
    )
    return metrics


def region_area_total_m2(regions: list[EvidenceRegion]) -> float:
    total = 0.0
    for region in regions:
        for metric in region.metrics:
            if metric.name in {"area_m2", "estimated_area"}:
                total += float(metric.value)
    return total


def enrich_region_metadata(
    region: EvidenceRegion,
    *,
    detector: str,
    detector_metadata: dict[str, Any],
) -> dict[str, Any]:
    metadata = dict(region.metadata)
    metadata.setdefault("evidence_type", "spectral_change")
    metadata.setdefault("evidence_modality", "optical")
    metadata.setdefault("claim_type", "none")
    if detector_metadata:
        metadata.setdefault("detector", detector)
        metadata.setdefault("algorithm", detector_metadata.get("algorithm"))
        metadata.setdefault("detector_version", detector_metadata.get("detector_version"))
        hint = detector_metadata.get("change_direction_hint")
        if hint:
            metadata.setdefault("change_direction_hint", hint)
        metadata.setdefault(
            "confidence_kind",
            detector_metadata.get("confidence_kind") or CONFIDENCE_KIND,
        )
    return metadata
