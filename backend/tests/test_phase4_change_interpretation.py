"""Phase 4 regression tests: evidence-grounded change interpretation and result contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.adapters.change.uploaded_bitemporal import UploadedBiTemporalChangeDetector
from app.adapters.imagery.uploaded.bi_temporal_bridge import build_change_detection_input
from app.core.config import get_settings
from app.evidence.bi_temporal_interpretation import (
    compact_detector_provenance,
    enrich_region_metadata,
    metrics_from_detector_metadata,
)
from app.evidence.multimodal_fusion import _annotate_cva
from app.schemas.bi_temporal_change import BiTemporalChangeResult
from app.schemas.change_understanding import ChangeUnderstandingToolInput
from app.schemas.domain import ChangeDetectionOutput, DataMode, EvidenceRegion, GeoJSONGeometry, Metric
from app.schemas.input import ImageFormat, ImageInput, ImageModality, ImageSource
from app.services.answer_engine import AnswerEngine
from app.services.query_controller import QueryController
from app.storage.factory import get_image_storage, get_metadata_registry
from app.tools.evidence.generate_evidence import GenerateEvidenceTool
from app.tools.temporal.change_understanding import ChangeUnderstandingTool
from tests.fixtures.rasters import SENTINEL2_BAND_NAMES, write_bi_temporal_scene


def _image_input(image_id: str, path: Path) -> ImageInput:
    with __import__("rasterio").open(path) as src:
        count = src.count
        width = src.width
        height = src.height
        crs = src.crs.to_string() if src.crs else "EPSG:4326"
    return ImageInput(
        id=image_id,
        modality=ImageModality.MULTISPECTRAL,
        format=ImageFormat.GEOTIFF,
        filename=path.name,
        width=width,
        height=height,
        file_size_bytes=path.stat().st_size,
        georeferenced=True,
        crs=crs,
        bounds=[77.59, 12.97, 77.61, 12.99],
        band_names=SENTINEL2_BAND_NAMES,
        source=ImageSource.UPLOAD,
        acquisition_datetime=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )


def _register_pair(tmp_path: Path, scenario: str = "vegetation_loss") -> tuple[ImageInput, ImageInput]:
    earlier_path = tmp_path / "earlier.tif"
    later_path = tmp_path / "later.tif"
    write_bi_temporal_scene(earlier_path, role="earlier", scenario=scenario)  # type: ignore[arg-type]
    write_bi_temporal_scene(later_path, role="later", scenario=scenario)  # type: ignore[arg-type]

    storage = get_image_storage()
    earlier_id = "4" * 32
    later_id = "5" * 32
    for image_id, src_path in ((earlier_id, earlier_path), (later_id, later_path)):
        with src_path.open("rb") as handle:
            storage.save(image_id, ".tif", handle)

    earlier = _image_input(earlier_id, earlier_path)
    later = _image_input(later_id, later_path).model_copy(
        update={
            "id": later_id,
            "filename": "later.tif",
            "acquisition_datetime": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
    )
    registry = get_metadata_registry()
    registry.save(earlier)
    registry.save(later)
    return earlier, later


def _sample_detector_metadata() -> dict:
    return {
        "algorithm": "uploaded_bi_temporal_index_diff",
        "detector_version": "1.0.0",
        "primary_index": "ndvi",
        "change_direction_hint": "vegetation_loss",
        "histogram_confidence": 0.9,
        "confidence_kind": "histogram_separability",
        "changed_pixel_count": 100,
        "total_pixel_count": 4096,
        "changed_percentage": 2.4414,
        "area_m2": 41000.0,
        "area_ha": 4.1,
        "area_km2": 0.041,
        "region_count": 1,
        "pipeline_stage_names": ["input_validation", "raster_loading"],
        "pipeline_stages": [{"stage": "input_validation", "status": "completed", "duration_ms": 1.0}],
        "inputs": {
            "earlier_image_id": "a" * 32,
            "later_image_id": "b" * 32,
            "earlier_source_ref": f"upload://{'a' * 32}",
            "later_source_ref": f"upload://{'b' * 32}",
            "earlier_filename": "earlier.tif",
            "later_filename": "later.tif",
        },
        "raster": {"bands": 5, "height": 64, "width": 64, "crs": "EPSG:4326"},
        "crs": "EPSG:4326",
        "coregistration_performed": False,
        "positional_band_fallback_used": True,
    }


@pytest.fixture(autouse=True)
def clear_caches(tmp_path, monkeypatch):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(upload_root))
    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "bi_temporal")
    get_settings.cache_clear()
    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    yield
    get_settings.cache_clear()
    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()


@pytest.mark.asyncio
async def test_change_understanding_uses_detector_scene_metrics(tmp_path):
    earlier, later = _register_pair(tmp_path, "vegetation_loss")
    detections = await UploadedBiTemporalChangeDetector().detect(
        build_change_detection_input(earlier, later, query_hint="vegetation loss")
    )
    output = await ChangeUnderstandingTool().execute(
        ChangeUnderstandingToolInput(
            query="What vegetation change occurred?",
            earlier=earlier,
            later=later,
            detections=detections,
        )
    )
    result = output.result
    assert result.scene_metrics is not None
    assert result.scene_metrics.area_ha is not None
    assert result.scene_metrics.changed_percentage is not None
    assert result.detector_summary is not None
    assert result.detector_summary.primary_index == detections.detector_metadata["primary_index"]
    assert result.detector_summary.change_direction_hint is not None
    assert result.confidence_kind == "histogram_separability"
    assert "NDVI" in result.change_summary or "ndvi" in result.change_summary.lower()
    assert "consistent with" in result.change_summary.lower()
    assert "deforestation" not in result.change_summary.lower()
    assert "occurred" not in result.change_summary.lower()


@pytest.mark.asyncio
async def test_answer_engine_uses_histogram_separability_wording(tmp_path):
    earlier, later = _register_pair(tmp_path, "flood")
    understanding = await ChangeUnderstandingTool().execute(
        ChangeUnderstandingToolInput(
            query="Where did water expand?",
            earlier=earlier,
            later=later,
            detections=await UploadedBiTemporalChangeDetector().detect(
                build_change_detection_input(earlier, later, query_hint="flood")
            ),
        )
    )
    from app.schemas.domain import QueryRequest

    answer = AnswerEngine().compose_bi_temporal_change(
        QueryRequest(
            query="Where did water expand?",
            earlier_image_id=earlier.id,
            later_image_id=later.id,
        ),
        understanding.result,
    )
    assert "Histogram separability score" in answer
    assert "not model accuracy" in answer.lower()
    assert "90% confident" not in answer.lower()
    assert "flood occurred" not in answer.lower()
    if understanding.result.detector_summary:
        hint = understanding.result.detector_summary.change_direction_hint
        if hint and hint != "no_change":
            assert "direction hint" in answer.lower() or "consistent with" in answer.lower()


def test_metrics_from_detector_metadata_promotes_area_fields():
    metrics = metrics_from_detector_metadata(_sample_detector_metadata(), source="uploaded_bi_temporal")
    names = {metric.name for metric in metrics}
    assert {"area_ha", "changed_percentage", "histogram_confidence", "primary_index", "confidence_kind"} <= names


@pytest.mark.asyncio
async def test_generate_evidence_preserves_detector_metrics():
    region = EvidenceRegion(
        id="change-region-01",
        geometry=GeoJSONGeometry(type="Polygon", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]),
        type="spectral_change",
        confidence=0.9,
        metrics=[Metric(name="area_m2", value=100.0, unit="m²", source="uploaded_bi_temporal")],
        source="uploaded_bi_temporal",
        metadata={"evidence_type": "spectral_change", "evidence_modality": "optical", "claim_type": "none"},
    )
    from app.schemas.domain import GenerateEvidenceInput, ImageryResult, ImageryScene, SensorType, SpatialMetadata

    imagery = ImageryResult(
        source="upload",
        mode=DataMode.DEVELOPMENT,
        sensor=SensorType.SENTINEL_2,
        scenes=[ImageryScene(scene_id="a", acquisition_date=datetime(2023, 1, 1).date())],
        spatial=SpatialMetadata(bbox=[0, 0, 1, 1]),
    )
    output = await GenerateEvidenceTool().execute(
        GenerateEvidenceInput(
            query="change?",
            imagery=imagery,
            fused_regions=[region],
            fusion_metadata={
                "source": "uploaded_bi_temporal_cva",
                "detector_metadata": _sample_detector_metadata(),
            },
        )
    )
    metric_names = {metric.name for metric in output.metrics}
    assert "area_ha" in metric_names
    assert "histogram_confidence" in metric_names


def test_region_metadata_compatible_with_fusion():
    region = EvidenceRegion(
        id="change-region-01",
        geometry=GeoJSONGeometry(type="Polygon", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]),
        type="spectral_change",
        confidence=0.9,
        metrics=[],
        source="uploaded_bi_temporal",
        metadata={"evidence_type": "spectral_change", "evidence_modality": "optical", "claim_type": "none"},
    )
    metadata = enrich_region_metadata(
        region,
        detector="uploaded_bi_temporal",
        detector_metadata=_sample_detector_metadata(),
    )
    enriched = region.model_copy(update={"metadata": metadata})
    annotated = _annotate_cva(enriched)
    assert annotated.type == "spectral_change"
    assert annotated.metadata["evidence_type"] == "spectral_change"
    assert annotated.metadata["change_direction_hint"] == "vegetation_loss"


def test_inference_metadata_has_no_filesystem_paths():
    compact = compact_detector_provenance(_sample_detector_metadata())
    serialized = str(compact)
    assert "/Users/" not in serialized
    assert "/private/" not in serialized
    assert "upload://" in serialized


@pytest.mark.asyncio
async def test_image_provenance_exposed_on_result(tmp_path):
    earlier, later = _register_pair(tmp_path)
    understanding = await ChangeUnderstandingTool().execute(
        ChangeUnderstandingToolInput(
            query="What changed?",
            earlier=earlier,
            later=later,
            detections=await UploadedBiTemporalChangeDetector().detect(
                build_change_detection_input(earlier, later)
            ),
        )
    )
    provenance = understanding.result.image_provenance
    assert provenance is not None
    assert provenance.earlier_source_ref == f"upload://{earlier.id}"
    assert provenance.later_source_ref == f"upload://{later.id}"
    assert provenance.earlier_filename == earlier.filename
    assert provenance.later_filename == later.filename


@pytest.mark.asyncio
async def test_pipeline_trace_preserved_in_inference_metadata(tmp_path):
    earlier, later = _register_pair(tmp_path)
    detections = await UploadedBiTemporalChangeDetector().detect(
        build_change_detection_input(earlier, later)
    )
    understanding = await ChangeUnderstandingTool().execute(
        ChangeUnderstandingToolInput(
            query="What changed?",
            earlier=earlier,
            later=later,
            detections=detections,
        )
    )
    inference = understanding.result.inference_metadata
    assert inference["pipeline_stages"]
    assert len(inference["pipeline_stages"]) == 12
    assert inference["detector_metadata"]["primary_index"] is not None


@pytest.mark.asyncio
async def test_deterministic_detector_summary_unchanged(monkeypatch, tmp_path):
    from app.adapters.change.deterministic import DeterministicChangeDetector
    from app.adapters.imagery.uploaded.bi_temporal_bridge import build_change_detection_input
    from app.schemas.domain import AOI, GeoJSONGeometry, ImageryResult, ImageryScene, SensorType, SpatialMetadata

    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "deterministic")
    get_settings.cache_clear()

    earlier, later = _register_pair(tmp_path)
    imagery = ImageryResult(
        source="upload",
        mode=DataMode.DEVELOPMENT,
        sensor=SensorType.SENTINEL_2,
        scenes=[
            ImageryScene(scene_id=earlier.id, acquisition_date=datetime(2023, 1, 1).date()),
            ImageryScene(scene_id=later.id, acquisition_date=datetime(2024, 1, 1).date()),
        ],
        spatial=SpatialMetadata(bbox=earlier.bounds or [0, 0, 1, 1]),
    )
    payload = build_change_detection_input(earlier, later)
    payload = payload.model_copy(
        update={
            "aoi": AOI(
                geometry=GeoJSONGeometry(
                    type="Polygon",
                    coordinates=[[[77.59, 12.97], [77.61, 12.97], [77.61, 12.99], [77.59, 12.99], [77.59, 12.97]]],
                )
            ),
            "imagery": imagery,
        }
    )
    detections = await DeterministicChangeDetector().detect(payload)
    understanding = await ChangeUnderstandingTool().execute(
        ChangeUnderstandingToolInput(
            query="What changed?",
            earlier=earlier,
            later=later,
            detections=detections,
        )
    )
    assert understanding.result.provider.value == "development"
    assert understanding.result.scene_metrics is None
    assert "Detected" in understanding.result.change_summary


def test_compact_provenance_preserves_configuration_snapshot():
    meta = _sample_detector_metadata()
    meta["configuration"] = {"otsu_enabled": True, "open_radius": 1}
    compact = compact_detector_provenance(meta)
    assert compact["configuration"]["otsu_enabled"] is True
