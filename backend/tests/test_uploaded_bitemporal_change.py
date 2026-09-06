"""Unit and integration tests for uploaded bi-temporal change detection."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from app.adapters.change.bi_temporal.confidence import compute_confidence
from app.adapters.change.bi_temporal.detector import detect_changes, otsu_threshold, suppress_pseudo_changes
from app.adapters.change.bi_temporal.indices import build_band_map, extract_index, select_primary_index
from app.adapters.change.bi_temporal.pipeline import BiTemporalPipeline
from app.adapters.change.bi_temporal.raster_io import load_raster, match_raster, needs_coregistration
from app.adapters.change.factory import get_upload_change_detector
from app.adapters.change.uploaded_bitemporal import UploadedBiTemporalChangeDetector
from app.adapters.imagery.uploaded.bi_temporal_bridge import build_change_detection_input
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.schemas.domain import DataMode
from app.schemas.input import ImageFormat, ImageInput, ImageModality, ImageSource
from app.storage.factory import get_image_storage, get_metadata_registry
from app.tools.temporal.detect_change import DetectChangeTool
from tests.fixtures.rasters import (
    SENTINEL2_BAND_NAMES,
    _scenario_arrays,
    write_bi_temporal_scene,
    write_geotiff,
    write_invalid_tiff,
    write_multispectral_geotiff,
)


def _image_input(image_id: str, path: Path, *, band_names: list[str] | None = None) -> ImageInput:
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
        band_names=band_names or [f"band_{i + 1}" for i in range(count)],
        source=ImageSource.UPLOAD,
        acquisition_datetime=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )


def _register_pair(tmp_path: Path, scenario: str) -> tuple[ImageInput, ImageInput]:
    earlier_path = tmp_path / "earlier.tif"
    later_path = tmp_path / "later.tif"
    write_bi_temporal_scene(earlier_path, role="earlier", scenario=scenario)  # type: ignore[arg-type]
    write_bi_temporal_scene(later_path, role="later", scenario=scenario)  # type: ignore[arg-type]

    storage = get_image_storage()
    earlier_id = "1" * 31 + "1"
    later_id = "1" * 31 + "2"
    for image_id, src_path in ((earlier_id, earlier_path), (later_id, later_path)):
        with src_path.open("rb") as handle:
            storage.save(image_id, ".tif", handle)

    earlier = _image_input(earlier_id, earlier_path, band_names=SENTINEL2_BAND_NAMES).model_copy(
        update={"acquisition_datetime": datetime(2023, 1, 1, tzinfo=timezone.utc)}
    )
    later = _image_input(later_id, later_path, band_names=SENTINEL2_BAND_NAMES).model_copy(
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


@pytest.mark.asyncio
async def test_vegetation_loss_detection(tmp_path):
    earlier, later = _register_pair(tmp_path, "vegetation_loss")
    payload = build_change_detection_input(earlier, later, query_hint="vegetation loss")
    output = await UploadedBiTemporalChangeDetector().detect(payload)

    assert output.detector == "uploaded_bi_temporal"
    assert output.detector_metadata["primary_index"] == "ndvi"
    assert output.raw_detection_count >= 1
    assert output.regions[0].geometry.type == "Polygon"
    assert output.detector_metadata["histogram_confidence"] >= 0.0
    assert output.detector_metadata["area_m2"] > 0
    assert len(output.detector_metadata["pipeline_stages"]) == 12


@pytest.mark.asyncio
async def test_flood_detection_uses_ndwi(tmp_path):
    earlier, later = _register_pair(tmp_path, "flood")
    payload = build_change_detection_input(earlier, later, query_hint="flood water expansion")
    output = await UploadedBiTemporalChangeDetector().detect(payload)
    assert output.detector_metadata["primary_index"] == "ndwi"
    assert output.raw_detection_count >= 1


@pytest.mark.asyncio
async def test_urban_detection_uses_ndbi(tmp_path):
    earlier, later = _register_pair(tmp_path, "urban")
    payload = build_change_detection_input(earlier, later, query_hint="urban built-up growth")
    output = await UploadedBiTemporalChangeDetector().detect(payload)
    assert output.detector_metadata["primary_index"] == "ndbi"
    assert output.raw_detection_count >= 1


def test_pseudo_change_suppression_reduces_uniform_shift():
    idx_t1 = np.full((64, 64), 0.35, dtype=np.float32)
    idx_t2 = np.full((64, 64), 0.55, dtype=np.float32)
    diff = np.abs(idx_t2 - idx_t1)
    suppressed, n_removed = suppress_pseudo_changes(
        diff, idx_t1, idx_t2, window_size=9, uniformity_threshold=0.05
    )
    assert n_removed > 0
    assert float(suppressed.sum()) < float(diff.sum())


def test_otsu_edge_cases():
    empty = np.zeros((8, 8), dtype=np.float32)
    mask, thresh = otsu_threshold(empty)
    assert thresh == 0.0
    assert mask.sum() == 0

    constant = np.full((8, 8), 3.14, dtype=np.float32)
    mask, thresh = otsu_threshold(constant)
    assert mask.sum() == 0

    nan_array = np.full((8, 8), np.nan, dtype=np.float32)
    mask, thresh = otsu_threshold(nan_array)
    assert np.isfinite(thresh)
    assert mask.sum() == 0


def test_confidence_is_separability_not_accuracy():
    diff = np.zeros((32, 32), dtype=np.float32)
    diff[10:20, 10:20] = 0.8
    mask = diff > 0.4
    score = compute_confidence(diff, mask, 0.4)
    assert 0.0 <= score <= 1.0


def test_coregistration_on_resolution_mismatch(tmp_path):
    earlier_path = tmp_path / "t1.tif"
    later_path = tmp_path / "t2.tif"
    t1, t2 = _scenario_arrays("vegetation_loss")
    write_multispectral_geotiff(earlier_path, t1, pixel_size=0.0001)
    write_multispectral_geotiff(later_path, t2, pixel_size=0.0002, origin_lon=77.595)
    r1 = load_raster(earlier_path)
    r2 = load_raster(later_path)
    assert needs_coregistration(r1, r2)
    aligned = match_raster(r2, r1)
    assert aligned.height == r1.height and aligned.width == r1.width


@pytest.mark.asyncio
async def test_no_overlap_rejected(tmp_path):
    earlier_path = tmp_path / "e.tif"
    later_path = tmp_path / "l.tif"
    write_bi_temporal_scene(earlier_path, role="earlier")
    write_bi_temporal_scene(later_path, role="later", origin_lon=80.0)
    earlier = _image_input("c" * 32, earlier_path)
    later = _image_input("d" * 32, later_path).model_copy(
        update={
            "acquisition_datetime": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "bounds": [80.0, 12.97, 80.2, 12.99],
        }
    )
    pipeline = BiTemporalPipeline()
    with pytest.raises(SatQueryError) as exc:
        pipeline.run(earlier_path, later_path, earlier, later)
    assert exc.value.code == "spatial_overlap"


@pytest.mark.asyncio
async def test_invalid_raster_rejected(tmp_path):
    from app.adapters.change.bi_temporal.validator import validate_raster_readable

    bad = tmp_path / "bad.tif"
    write_invalid_tiff(bad)
    with pytest.raises(SatQueryError) as exc:
        validate_raster_readable(bad)
    assert exc.value.code == "invalid_raster"


def test_geojson_validity(tmp_path):
    earlier, later = _register_pair(tmp_path, "vegetation_loss")
    result = BiTemporalPipeline().run(
        get_image_storage().path_for(earlier.id, ".tif"),
        get_image_storage().path_for(later.id, ".tif"),
        earlier,
        later,
    )
    assert result.regions
    for region in result.regions:
        json.dumps(region.geometry.model_dump())
        assert region.geometry.type == "Polygon"
        assert len(region.geometry.coordinates[0]) >= 4


@pytest.mark.asyncio
async def test_deterministic_repeatability(tmp_path):
    earlier, later = _register_pair(tmp_path, "vegetation_loss")
    payload = build_change_detection_input(earlier, later)
    out1 = await UploadedBiTemporalChangeDetector().detect(payload)
    out2 = await UploadedBiTemporalChangeDetector().detect(payload)
    assert out1.raw_detection_count == out2.raw_detection_count
    assert out1.detector_metadata["histogram_confidence"] == out2.detector_metadata["histogram_confidence"]


def test_single_band_fallback(tmp_path):
    path = tmp_path / "single.tif"
    write_geotiff(path, bands=1)
    arr = load_raster(path).array
    band_map = build_band_map(["band_1"], 1)
    assert select_primary_index(1, band_map) == "band_1"
    idx = extract_index(arr, "band_1", band_map)
    assert idx is not None


def test_factory_upload_routing(monkeypatch):
    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "bi_temporal")
    get_settings.cache_clear()
    assert isinstance(get_upload_change_detector(), UploadedBiTemporalChangeDetector)


@pytest.mark.asyncio
async def test_detect_change_tool_integration(tmp_path):
    earlier, later = _register_pair(tmp_path, "vegetation_loss")
    payload = build_change_detection_input(earlier, later)
    output = await DetectChangeTool(detector=UploadedBiTemporalChangeDetector()).execute(payload)
    assert output.mode == DataMode.DEVELOPMENT
    assert output.detector == "uploaded_bi_temporal"
