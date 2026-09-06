"""Phase 3 regression tests: upload integration polish, provenance, and routing."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.adapters.change.bi_temporal.errors import BiTemporalPipelineError
from app.adapters.change.bi_temporal.pipeline import PIPELINE_STAGE_NAMES, BiTemporalPipeline
from app.adapters.change.deterministic import DeterministicChangeDetector
from app.adapters.change.factory import get_change_detector, get_upload_change_detector
from app.adapters.change.uploaded_bitemporal import UploadedBiTemporalChangeDetector
from app.adapters.imagery.uploaded.bi_temporal_bridge import build_change_detection_input
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.evidence.multimodal_fusion import _annotate_cva
from app.schemas.domain import DataMode, SensorType
from app.schemas.input import ImageFormat, ImageInput, ImageModality, ImageSource
from app.storage.factory import get_image_storage, get_metadata_registry
from tests.fixtures.rasters import SENTINEL2_BAND_NAMES, write_bi_temporal_scene, write_invalid_tiff


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
    earlier_id = "e" * 32
    later_id = "f" * 32
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


def test_upload_factory_routes_bi_temporal(monkeypatch):
    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "bi_temporal")
    get_settings.cache_clear()
    assert isinstance(get_upload_change_detector(), UploadedBiTemporalChangeDetector)


def test_upload_factory_routes_deterministic(monkeypatch):
    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "deterministic")
    get_settings.cache_clear()
    assert isinstance(get_upload_change_detector(), DeterministicChangeDetector)


def test_upload_factory_rejects_invalid_config(monkeypatch):
    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "earth_engine")
    get_settings.cache_clear()
    with pytest.raises(SatQueryError) as exc:
        get_upload_change_detector()
    assert exc.value.code == "change_detector_misconfigured"


def test_catalog_factory_unchanged_development(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "development")
    monkeypatch.setenv("CHANGE_DETECTOR", "development")
    get_settings.cache_clear()
    assert isinstance(get_change_detector(DataMode.DEVELOPMENT), DeterministicChangeDetector)


def test_catalog_factory_unchanged_earth_engine(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "earth_engine")
    monkeypatch.setenv("CHANGE_DETECTOR", "earth_engine")
    get_settings.cache_clear()
    from app.adapters.change.earth_engine import EarthEngineChangeDetector

    assert isinstance(get_change_detector(DataMode.EARTH_ENGINE), EarthEngineChangeDetector)


def test_catalog_factory_unchanged_sar(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "earth_engine")
    monkeypatch.setenv("CHANGE_DETECTOR", "earth_engine")
    monkeypatch.setenv("SAR_CHANGE_DETECTOR", "earth_engine")
    get_settings.cache_clear()
    from app.adapters.change.earth_engine import EarthEngineSARChangeDetector

    assert isinstance(
        get_change_detector(DataMode.EARTH_ENGINE, SensorType.SENTINEL_1),
        EarthEngineSARChangeDetector,
    )


def _assert_trace_structure(stages: list[dict]) -> None:
    assert len(stages) == len(PIPELINE_STAGE_NAMES)
    stage_names = [entry["stage"] for entry in stages]
    assert stage_names == list(PIPELINE_STAGE_NAMES)
    for entry in stages:
        assert entry["status"] in {"completed", "failed", "skipped"}
        assert isinstance(entry["duration_ms"], (int, float))
        assert "tool" in entry
        assert "observation" in entry
        assert "metadata" in entry
        metadata = entry["metadata"]
        assert isinstance(metadata, dict)
        for value in metadata.values():
            assert not isinstance(value, (list, dict)) or len(str(value)) < 5000


@pytest.mark.asyncio
async def test_detector_provenance_metadata(tmp_path):
    earlier, later = _register_pair(tmp_path)
    payload = build_change_detection_input(earlier, later, query_hint="vegetation")
    output = await UploadedBiTemporalChangeDetector().detect(payload)
    meta = output.detector_metadata

    assert meta["algorithm"] == "uploaded_bi_temporal_index_diff"
    assert meta["earlier_image_id"] == earlier.id
    assert meta["later_image_id"] == later.id
    assert meta["inputs"]["earlier_source_ref"] == f"upload://{earlier.id}"
    assert meta["inputs"]["later_source_ref"] == f"upload://{later.id}"
    assert meta["raster"]["height"] == earlier.height
    assert meta["raster"]["width"] == earlier.width
    assert meta["crs"] is not None
    assert isinstance(meta["band_mapping"], dict)
    assert "mapping_source" in meta
    assert isinstance(meta["positional_band_fallback_used"], bool)
    assert isinstance(meta["coregistration_performed"], bool)
    assert isinstance(meta["configuration"], dict)
    assert meta["configuration"]["otsu_enabled"] is True
    _assert_trace_structure(meta["pipeline_stages"])


@pytest.mark.asyncio
async def test_evidence_regions_compatible_with_fusion(tmp_path):
    earlier, later = _register_pair(tmp_path)
    payload = build_change_detection_input(earlier, later)
    output = await UploadedBiTemporalChangeDetector().detect(payload)
    assert output.regions
    for region in output.regions:
        assert region.type == "spectral_change"
        assert region.metadata.get("evidence_type") == "spectral_change"
        assert region.metadata.get("evidence_modality") == "optical"
        assert region.metadata.get("claim_type") == "none"
        annotated = _annotate_cva(region)
        assert annotated.type == "spectral_change"
        assert annotated.metadata["evidence_type"] == "spectral_change"


def test_pipeline_failure_surfaces_satquery_error_with_stages(tmp_path):
    earlier_path = tmp_path / "e.tif"
    later_path = tmp_path / "l.tif"
    write_bi_temporal_scene(earlier_path, role="earlier")
    write_bi_temporal_scene(later_path, role="later", origin_lon=80.0)
    earlier = _image_input("a" * 32, earlier_path)
    later = _image_input("b" * 32, later_path).model_copy(
        update={
            "acquisition_datetime": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "bounds": [80.0, 12.97, 80.2, 12.99],
        }
    )
    with pytest.raises(BiTemporalPipelineError) as exc:
        BiTemporalPipeline().run(earlier_path, later_path, earlier, later)
    assert exc.value.code == "spatial_overlap"
    assert exc.value.pipeline_stages
    assert exc.value.pipeline_stages[0]["stage"] == "input_validation"
    assert exc.value.pipeline_stages[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_invalid_raster_failure_is_satquery_not_rasterio(tmp_path):
    bad = tmp_path / "bad.tif"
    write_invalid_tiff(bad)
    earlier = ImageInput(
        id="c" * 32,
        modality=ImageModality.MULTISPECTRAL,
        format=ImageFormat.GEOTIFF,
        filename="bad.tif",
        width=64,
        height=64,
        file_size_bytes=bad.stat().st_size,
        georeferenced=True,
        crs="EPSG:4326",
        bounds=[77.59, 12.97, 77.61, 12.99],
        band_names=SENTINEL2_BAND_NAMES,
        source=ImageSource.UPLOAD,
        acquisition_datetime=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    later = earlier.model_copy(
        update={
            "id": "d" * 32,
            "acquisition_datetime": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
    )
    storage = get_image_storage()
    for image in (earlier, later):
        with bad.open("rb") as handle:
            storage.save(image.id, ".tif", handle)
        get_metadata_registry().save(image)

    payload = build_change_detection_input(earlier, later)
    with pytest.raises(SatQueryError) as exc:
        await UploadedBiTemporalChangeDetector().detect(payload)
    assert exc.value.code == "invalid_raster"
    assert "Rasterio" not in exc.value.message
    assert "rasterio" not in exc.value.message.lower()


@pytest.mark.asyncio
async def test_deterministic_repeatability_phase3(tmp_path):
    earlier, later = _register_pair(tmp_path)
    payload = build_change_detection_input(earlier, later)
    detector = UploadedBiTemporalChangeDetector()
    out1 = await detector.detect(payload)
    out2 = await detector.detect(payload)
    assert out1.raw_detection_count == out2.raw_detection_count
    assert out1.detector_metadata["otsu_threshold"] == out2.detector_metadata["otsu_threshold"]
    assert [s["stage"] for s in out1.detector_metadata["pipeline_stages"]] == [
        s["stage"] for s in out2.detector_metadata["pipeline_stages"]
    ]
