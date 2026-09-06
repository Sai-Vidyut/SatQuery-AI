"""End-to-end bi-temporal change detection pipeline for uploaded GeoTIFF pairs."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.adapters.change.bi_temporal.confidence import compute_confidence
from app.adapters.change.bi_temporal.config import (
    DEFAULT_CONFIG,
    DETECTOR_VERSION,
    SOURCE_LABEL,
    BiTemporalConfig,
    config_snapshot,
)
from app.adapters.change.bi_temporal.detector import detect_changes
from app.adapters.change.bi_temporal.errors import BiTemporalPipelineError, wrap_pipeline_failure
from app.adapters.change.bi_temporal.indices import (
    build_band_map_selection,
    extract_index,
    select_primary_index,
)
from app.adapters.change.bi_temporal.metrics import (
    classify_change_direction_hint,
    compute_area_metrics,
    pixel_area_m2,
)
from app.adapters.change.bi_temporal.morphology import clean_mask, label_components
from app.adapters.change.bi_temporal.raster_io import (
    load_raster,
    match_raster,
    needs_coregistration,
    polygonize_mask,
)
from app.adapters.change.bi_temporal.trace import PipelineStageRecorder
from app.adapters.change.bi_temporal.validator import validate_raster_pair
from app.core.errors import SatQueryError
from app.schemas.domain import EvidenceRegion, GeoJSONGeometry, Metric
from app.schemas.input import ImageInput

PIPELINE_STAGE_NAMES = (
    "input_validation",
    "raster_loading",
    "coregistration",
    "index_selection",
    "index_computation",
    "temporal_difference",
    "pseudo_change_suppression",
    "thresholding",
    "morphology",
    "connected_components",
    "confidence",
    "polygonization",
)


@dataclass
class BiTemporalPipelineResult:
    regions: list[EvidenceRegion]
    detector_metadata: dict[str, Any] = field(default_factory=dict)


def _crs_label(crs) -> str | None:
    if crs is None:
        return None
    epsg = crs.to_epsg() if hasattr(crs, "to_epsg") else None
    if epsg:
        return f"EPSG:{epsg}"
    return crs.to_string() if hasattr(crs, "to_string") else str(crs)


def _input_provenance(earlier_meta: ImageInput, later_meta: ImageInput) -> dict[str, Any]:
    return {
        "earlier_image_id": earlier_meta.id,
        "later_image_id": later_meta.id,
        "earlier_filename": earlier_meta.filename,
        "later_filename": later_meta.filename,
        "earlier_source_ref": f"upload://{earlier_meta.id}",
        "later_source_ref": f"upload://{later_meta.id}",
        "earlier_modality": earlier_meta.modality.value,
        "later_modality": later_meta.modality.value,
        "earlier_band_names": earlier_meta.band_names,
        "later_band_names": later_meta.band_names,
    }


def _raster_provenance(raster) -> dict[str, Any]:
    return {
        "bands": raster.bands,
        "height": raster.height,
        "width": raster.width,
        "crs": _crs_label(raster.crs),
    }


def _polygon_area_m2(coords: list[list[float]], mean_lat: float) -> float:
    if len(coords) < 3:
        return 0.0
    ring = coords[:-1] if coords[0] == coords[-1] else coords
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * np.cos(np.radians(mean_lat))
    area = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i][0] * lon_scale, ring[i][1] * lat_scale
        x2, y2 = ring[(i + 1) % len(ring)][0] * lon_scale, ring[(i + 1) % len(ring)][1] * lat_scale
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _features_to_regions(
    features: list[dict[str, Any]],
    *,
    histogram_confidence: float,
    primary_index: str,
    min_area_m2: float,
    max_regions: int,
    pixel_area: float,
) -> list[EvidenceRegion]:
    parsed: list[tuple[float, EvidenceRegion]] = []

    for idx, feature in enumerate(features):
        geom = feature.get("geometry")
        if not geom or geom.get("type") != "Polygon":
            continue
        coords = geom.get("coordinates")
        if not coords:
            continue

        ring = coords[0]
        mean_lat = sum(p[1] for p in ring) / len(ring)
        area_m2 = _polygon_area_m2(ring, mean_lat)
        if area_m2 < min_area_m2:
            area_m2 = float(feature.get("properties", {}).get("area_px", 0)) * pixel_area
        if area_m2 < min_area_m2:
            continue

        region = EvidenceRegion(
            id=f"change-region-{idx + 1:02d}",
            geometry=GeoJSONGeometry(type="Polygon", coordinates=coords),
            type="spectral_change",
            confidence=histogram_confidence,
            metrics=[
                Metric(name="area_m2", value=round(area_m2, 1), unit="m²", source=SOURCE_LABEL),
                Metric(
                    name="area_km2",
                    value=round(area_m2 / 1_000_000.0, 6),
                    unit="km²",
                    source=SOURCE_LABEL,
                ),
                Metric(
                    name="histogram_confidence",
                    value=histogram_confidence,
                    unit="ratio",
                    source=SOURCE_LABEL,
                ),
                Metric(name="primary_index", value=primary_index, unit=None, source=SOURCE_LABEL),
            ],
            source=SOURCE_LABEL,
            metadata={
                "detector_version": DETECTOR_VERSION,
                "primary_index": primary_index,
                "confidence_kind": "histogram_separability",
                "evidence_type": "spectral_change",
                "evidence_modality": "optical",
                "claim_type": "none",
            },
        )
        parsed.append((area_m2, region))

    parsed.sort(key=lambda item: item[0], reverse=True)
    limited = parsed[:max_regions]
    regions: list[EvidenceRegion] = []
    for rank, (_, region) in enumerate(limited, start=1):
        regions.append(region.model_copy(update={"id": f"change-region-{rank:02d}"}))
    return regions


class BiTemporalPipeline:
    def __init__(self, config: BiTemporalConfig | None = None) -> None:
        self._config = config or DEFAULT_CONFIG

    def run(
        self,
        earlier_path: Path,
        later_path: Path,
        earlier_meta: ImageInput,
        later_meta: ImageInput,
        *,
        query_hint: str = "",
    ) -> BiTemporalPipelineResult:
        cfg = self._config
        recorder = PipelineStageRecorder()
        total_t0 = time.perf_counter()

        try:
            recorder.run(
                "input_validation",
                "bi_temporal.validator",
                lambda: validate_raster_pair(earlier_path, later_path, earlier_meta, later_meta),
                observation="Raster pair validation passed.",
                metadata={
                    "earlier_file": earlier_path.name,
                    "later_file": later_path.name,
                },
                failure_code="invalid_raster",
                failure_message="Uploaded bi-temporal raster validation failed.",
            )

            raster_t1, raster_t2 = recorder.run(
                "raster_loading",
                "rasterio",
                lambda: (load_raster(earlier_path), load_raster(later_path)),
                observation="Loaded earlier and later uploaded rasters.",
                metadata={
                    "earlier_file": earlier_path.name,
                    "later_file": later_path.name,
                },
                failure_code="invalid_raster",
                failure_message="Unable to load uploaded bi-temporal rasters.",
            )
            recorder.stages[-1]["observation"] = (
                f"Loaded T1 {raster_t1.bands}x{raster_t1.height}x{raster_t1.width} and "
                f"T2 {raster_t2.bands}x{raster_t2.height}x{raster_t2.width}."
            )
            recorder.stages[-1]["metadata"] = {
                "earlier": _raster_provenance(raster_t1),
                "later": _raster_provenance(raster_t2),
            }

            coreg_required = needs_coregistration(raster_t1, raster_t2)

            def _coregister():
                nonlocal raster_t2
                if coreg_required:
                    raster_t2 = match_raster(raster_t2, raster_t1)
                return raster_t2

            recorder.run(
                "coregistration",
                "rasterio.warp",
                _coregister,
                observation=(
                    f"T2 aligned to T1 grid ({raster_t1.height}x{raster_t1.width})."
                    if coreg_required
                    else f"Grids aligned ({raster_t1.height}x{raster_t1.width}); no resampling."
                ),
                metadata={"coregistration_performed": coreg_required},
                failure_code="coregistration_failed",
                failure_message="Failed to co-register uploaded bi-temporal rasters.",
            )

            modality = "sar" if earlier_meta.modality.value == "sar" else "optical"
            band_selection = build_band_map_selection(
                earlier_meta.band_names,
                raster_t1.bands,
                modality=modality,
            )
            band_map = band_selection.band_map

            primary_index = select_primary_index(
                raster_t1.bands,
                band_map,
                modality=modality,
                query_hint=query_hint,
            )
            recorder.append(
                "index_selection",
                "bi_temporal.indices",
                observation=f"Selected primary index {primary_index.upper()}.",
                metadata={
                    "primary_index": primary_index,
                    "query_hint": query_hint or None,
                    "band_mapping": band_map,
                    "mapping_source": band_selection.mapping_source,
                    "positional_band_fallback_used": band_selection.positional_fallback_used,
                },
            )

            def _compute_indices():
                idx_t1 = extract_index(raster_t1.array, primary_index, band_map)
                idx_t2 = extract_index(raster_t2.array, primary_index, band_map)
                if idx_t1 is None or idx_t2 is None:
                    raise SatQueryError(
                        "index_unavailable",
                        f"Cannot compute index {primary_index} from uploaded bands.",
                        status_code=400,
                    )
                return idx_t1, idx_t2

            idx_t1, idx_t2 = recorder.run(
                "index_computation",
                f"bi_temporal.indices.{primary_index}",
                _compute_indices,
                observation=f"Computed {primary_index.upper()} for T1/T2.",
                metadata={"primary_index": primary_index},
                failure_code="index_unavailable",
            )

            det = detect_changes(
                idx_t1,
                idx_t2,
                smooth_sigma=cfg.smooth_sigma,
                suppress_pseudo=cfg.suppress_pseudo_changes,
                pseudo_window=cfg.pseudo_window_size,
                pseudo_uniformity_threshold=cfg.pseudo_uniformity_threshold,
                percentile_clip=cfg.otsu_percentile_clip,
                use_otsu=cfg.otsu_enabled,
            )

            recorder.append(
                "temporal_difference",
                "bi_temporal.detector",
                observation=f"Absolute differencing on {primary_index.upper()} complete.",
                metadata={"primary_index": primary_index},
            )
            recorder.append(
                "pseudo_change_suppression",
                "bi_temporal.detector.suppress_pseudo_changes",
                observation=(
                    f"STSF-inspired pseudo-change suppression removed {det['n_pseudo_removed']} px."
                ),
                metadata={
                    "enabled": cfg.suppress_pseudo_changes,
                    "n_pseudo_removed": det["n_pseudo_removed"],
                },
            )
            recorder.append(
                "thresholding",
                "bi_temporal.detector.otsu",
                observation=(
                    f"Otsu threshold={det['otsu_threshold']:.6f}; "
                    f"raw mask pixels={int(det['change_mask'].sum())}."
                ),
                metadata={
                    "otsu_enabled": cfg.otsu_enabled,
                    "otsu_threshold": det["otsu_threshold"],
                    "raw_changed_pixels": int(det["change_mask"].sum()),
                },
            )

            def _morphology():
                cleaned = clean_mask(
                    det["change_mask"],
                    open_radius=cfg.open_radius,
                    close_radius=cfg.close_radius,
                    min_area_px=cfg.min_region_area_px,
                )
                _, n_regions = label_components(cleaned)
                return cleaned, n_regions

            cleaned, n_regions = recorder.run(
                "morphology",
                "bi_temporal.morphology",
                _morphology,
                observation="Morphological cleaning applied to change mask.",
                metadata={
                    "open_radius": cfg.open_radius,
                    "close_radius": cfg.close_radius,
                    "min_region_area_px": cfg.min_region_area_px,
                },
            )
            recorder.stages[-1]["observation"] = (
                f"Cleaned mask: {int(cleaned.sum())} px in {n_regions} component(s)."
            )
            recorder.append(
                "connected_components",
                "bi_temporal.morphology.label_components",
                observation=f"Connected components: {n_regions}.",
                metadata={"component_count": n_regions},
            )

            histogram_confidence = compute_confidence(
                det["suppressed_diff"],
                cleaned,
                det["otsu_threshold"],
                imbalance_low=cfg.confidence_imbalance_low,
                imbalance_high=cfg.confidence_imbalance_high,
            )
            px_area = pixel_area_m2(raster_t1.transform)
            area_metrics = compute_area_metrics(cleaned, raster_t1.transform)
            area_metrics["region_count"] = n_regions
            direction_hint = classify_change_direction_hint(
                det["signed_diff"],
                cleaned,
                primary_index,
            )
            recorder.append(
                "confidence",
                "bi_temporal.confidence",
                observation=(
                    f"Histogram separability confidence={histogram_confidence:.4f} "
                    f"(detector confidence, not model accuracy)."
                ),
                metadata={
                    "histogram_confidence": histogram_confidence,
                    "confidence_kind": "histogram_separability",
                    "changed_area_ha": area_metrics["area_ha"],
                    "changed_percentage": area_metrics["changed_percentage"],
                },
            )

            def _polygonize():
                features = polygonize_mask(
                    cleaned,
                    raster_t1,
                    min_area_px=cfg.min_region_area_px,
                )
                regions = _features_to_regions(
                    features,
                    histogram_confidence=histogram_confidence,
                    primary_index=primary_index,
                    min_area_m2=cfg.min_region_area_m2,
                    max_regions=cfg.max_regions,
                    pixel_area=px_area,
                )
                return features, regions

            features, regions = recorder.run(
                "polygonization",
                "bi_temporal.raster_io.polygonize_mask",
                _polygonize,
                observation="Polygonized change mask into EvidenceRegion output.",
                metadata={"min_region_area_m2": cfg.min_region_area_m2},
            )
            recorder.stages[-1]["observation"] = (
                f"Polygonized {len(regions)} region(s) for EvidenceRegion output."
            )
            recorder.stages[-1]["metadata"] = {
                "feature_count": len(features),
                "region_count": len(regions),
                "min_region_area_m2": cfg.min_region_area_m2,
            }
            area_metrics["region_count"] = len(regions)

        except SatQueryError as exc:
            raise BiTemporalPipelineError(
                exc.code,
                exc.message,
                exc.status_code,
                pipeline_stages=recorder.stages,
                field=exc.field,
            ) from exc
        except Exception as exc:
            raise wrap_pipeline_failure(exc, pipeline_stages=recorder.stages) from exc

        total_ms = (time.perf_counter() - total_t0) * 1000
        metadata = {
            "algorithm": "uploaded_bi_temporal_index_diff",
            "detector_version": DETECTOR_VERSION,
            "primary_index": primary_index,
            "change_direction_hint": direction_hint,
            "histogram_confidence": histogram_confidence,
            "confidence_kind": "histogram_separability",
            "otsu_threshold": det["otsu_threshold"],
            "n_pseudo_removed": det["n_pseudo_removed"],
            "pseudo_change_suppression": "stsf_inspired",
            "changed_pixel_count": area_metrics["changed_pixel_count"],
            "total_pixel_count": area_metrics["total_pixel_count"],
            "changed_percentage": area_metrics["changed_percentage"],
            "area_m2": area_metrics["area_m2"],
            "area_ha": area_metrics["area_ha"],
            "area_km2": area_metrics["area_km2"],
            "region_count": len(regions),
            "pipeline_stages": recorder.stages,
            "pipeline_stage_names": list(PIPELINE_STAGE_NAMES),
            "total_processing_ms": round(total_ms, 1),
            "inputs": _input_provenance(earlier_meta, later_meta),
            "raster": _raster_provenance(raster_t1),
            "crs": _crs_label(raster_t1.crs),
            "band_mapping": band_map,
            "mapping_source": band_selection.mapping_source,
            "positional_band_fallback_used": band_selection.positional_fallback_used,
            "coregistration_performed": coreg_required,
            "configuration": config_snapshot(cfg),
            # Legacy flat fields retained for backward compatibility.
            "earlier_image_id": earlier_meta.id,
            "later_image_id": later_meta.id,
        }

        return BiTemporalPipelineResult(regions=regions, detector_metadata=metadata)
