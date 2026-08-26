from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.input import (
    AnalysisInputType,
    BiTemporalAnalysisInput,
    ImageFormat,
    ImageInput,
    ImageModality,
    ImageSource,
    OpticalSARPairAnalysisInput,
    SingleImageAnalysisInput,
)


def _sample_image(**overrides) -> ImageInput:
    base = dict(
        id="a" * 32,
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="scene.tif",
        width=100,
        height=100,
        file_size_bytes=1024,
        georeferenced=True,
        crs="EPSG:4326",
        bounds=[77.59, 12.97, 77.61, 12.99],
        source=ImageSource.UPLOAD,
    )
    base.update(overrides)
    return ImageInput(**base)


def test_valid_single_image_schema():
    payload = SingleImageAnalysisInput(image=_sample_image())
    assert payload.input_type == AnalysisInputType.SINGLE_IMAGE


def test_valid_bi_temporal_schema():
    earlier = _sample_image(id="b" * 32)
    later = _sample_image(id="c" * 32)
    payload = BiTemporalAnalysisInput(earlier=earlier, later=later)
    assert payload.earlier.id != payload.later.id


def test_valid_optical_sar_pair_schema():
    optical = _sample_image(modality=ImageModality.OPTICAL)
    sar = _sample_image(id="d" * 32, modality=ImageModality.SAR)
    payload = OpticalSARPairAnalysisInput(optical=optical, sar=sar)
    assert payload.sar.modality == ImageModality.SAR


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        ImageInput(
            id="e" * 32,
            modality=ImageModality.OPTICAL,
            format=ImageFormat.GEOTIFF,
            filename="x.tif",
            width=10,
            height=10,
            file_size_bytes=1,
            georeferenced=True,
            fake_field="nope",  # type: ignore[call-arg]
        )


def test_invalid_modality_enum():
    with pytest.raises(ValidationError):
        ImageInput(
            id="f" * 32,
            modality="radar",  # type: ignore[arg-type]
            format=ImageFormat.GEOTIFF,
            filename="x.tif",
            width=10,
            height=10,
            file_size_bytes=1,
            georeferenced=True,
        )
