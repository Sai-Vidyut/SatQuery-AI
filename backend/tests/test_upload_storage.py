from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from app.adapters.imagery.uploaded.metadata import probe_raster
from app.adapters.imagery.uploaded.validation import build_image_input
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.schemas.input import ImageFormat, ImageModality
from app.storage.local import LocalFilesystemStorage, assert_safe_image_id
from tests.fixtures.rasters import write_geotiff, write_invalid_tiff, write_png


@pytest.fixture
def upload_root(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(root))
    get_settings.cache_clear()
    from app.storage.factory import get_image_storage, get_metadata_registry

    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    yield root
    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    get_settings.cache_clear()


def test_storage_save_and_exists(upload_root):
    storage = LocalFilesystemStorage(upload_root)
    image_id = "a" * 32
    storage.save(image_id, ".tif", BytesIO(b"hello"))
    assert storage.exists(image_id, ".tif")


def test_storage_path_traversal_rejected(upload_root):
    storage = LocalFilesystemStorage(upload_root)
    with pytest.raises(SatQueryError) as exc:
        storage.open("../etc/passwd", ".tif")
    assert exc.value.code in {"invalid_image_id", "path_traversal"}


def test_assert_safe_image_id_rejects_bad_ids():
    with pytest.raises(SatQueryError):
        assert_safe_image_id("../../etc/passwd")


def test_probe_geotiff_metadata(upload_root):
    path = upload_root / "scene.tif"
    write_geotiff(path)
    probe = probe_raster(path, ImageFormat.GEOTIFF)
    assert probe.width == 64
    assert probe.height == 64
    assert probe.georeferenced is True
    assert probe.bounds is not None


def test_build_image_input_from_geotiff(upload_root):
    path = upload_root / "scene.tif"
    write_geotiff(path)
    image = build_image_input(
        image_id="b" * 32,
        path=path,
        original_filename="scene.tif",
        image_format=ImageFormat.GEOTIFF,
        modality=ImageModality.OPTICAL,
        benchmark_dataset=False,
    )
    assert image.georeferenced is True
    assert image.crs == "EPSG:4326"


def test_invalid_raster_rejected(upload_root):
    path = upload_root / "bad.tif"
    write_invalid_tiff(path)
    with pytest.raises(SatQueryError) as exc:
        build_image_input(
            image_id="c" * 32,
            path=path,
            original_filename="bad.tif",
            image_format=ImageFormat.GEOTIFF,
            modality=None,
            benchmark_dataset=False,
        )
    assert exc.value.code == "invalid_raster"


def test_png_requires_benchmark_flag_in_validation_layer(upload_root):
    path = upload_root / "bench.png"
    write_png(path)
    with pytest.raises(SatQueryError) as exc:
        from app.adapters.imagery.uploaded.validation import validate_extension_and_format

        validate_extension_and_format(".png", benchmark_dataset=False)
    assert exc.value.code == "benchmark_required"


def test_png_allowed_with_benchmark(upload_root):
    path = upload_root / "bench.png"
    write_png(path)
    image = build_image_input(
        image_id="d" * 32,
        path=path,
        original_filename="bench.png",
        image_format=ImageFormat.PNG,
        modality=ImageModality.OPTICAL,
        benchmark_dataset=True,
    )
    assert image.format == ImageFormat.PNG
    assert image.georeferenced is False
