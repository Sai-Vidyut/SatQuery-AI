from __future__ import annotations

import pytest

from app.adapters.imagery.uploaded.compatibility import (
    validate_bi_temporal,
    validate_optical_sar_pair,
    validate_single_image,
)
from app.schemas.input import ImageFormat, ImageInput, ImageModality, ImageSource


def _image(
    image_id: str,
    *,
    modality: ImageModality = ImageModality.OPTICAL,
    bounds: list[float] | None = None,
    width: int = 100,
    height: int = 100,
    crs: str | None = "EPSG:4326",
    benchmark: bool = False,
    fmt: ImageFormat = ImageFormat.GEOTIFF,
) -> ImageInput:
    return ImageInput(
        id=image_id,
        modality=modality,
        format=fmt,
        filename=f"{image_id}.tif",
        width=width,
        height=height,
        file_size_bytes=1024,
        georeferenced=True,
        crs=crs,
        bounds=bounds or [77.59, 12.97, 77.61, 12.99],
        source=ImageSource.UPLOAD,
        benchmark_dataset=benchmark,
    )


def test_single_image_valid():
    result = validate_single_image(_image("a" * 32))
    assert result.valid is True
    assert result.detected_input_type.value == "single_image"


def test_bi_temporal_overlap_pass():
    earlier = _image("b" * 32, bounds=[77.59, 12.97, 77.61, 12.99])
    later = _image("c" * 32, bounds=[77.59, 12.97, 77.61, 12.99])
    result = validate_bi_temporal(earlier, later)
    assert result.valid is True


def test_bi_temporal_non_overlapping_fails():
    earlier = _image("d" * 32, bounds=[77.59, 12.97, 77.61, 12.99])
    later = _image("e" * 32, bounds=[80.0, 12.97, 80.2, 12.99])
    result = validate_bi_temporal(earlier, later)
    assert result.valid is False
    assert any("overlap" in e.lower() for e in result.errors)


def test_bi_temporal_sar_rejected():
    earlier = _image("f" * 32)
    later = _image("0" * 32, modality=ImageModality.SAR)
    result = validate_bi_temporal(earlier, later)
    assert result.valid is False


def test_optical_sar_valid_with_warning():
    optical = _image("1" * 32, modality=ImageModality.OPTICAL)
    sar = _image("2" * 32, modality=ImageModality.SAR)
    result = validate_optical_sar_pair(optical, sar)
    assert result.valid is True
    assert any(c.check == "coregistration" for c in result.checks)


def test_optical_sar_invalid_modality_combo():
    optical = _image("3" * 32, modality=ImageModality.SAR)
    sar = _image("4" * 32, modality=ImageModality.SAR)
    result = validate_optical_sar_pair(optical, sar)
    assert result.valid is False


def test_dimension_mismatch_warns_not_fails():
    optical = _image("5" * 32, width=100, height=100)
    sar = _image("6" * 32, modality=ImageModality.SAR, width=200, height=200)
    result = validate_optical_sar_pair(optical, sar)
    assert result.valid is True
    assert result.warnings
