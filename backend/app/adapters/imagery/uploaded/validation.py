from __future__ import annotations

import re
import uuid
from pathlib import Path

from datetime import datetime

from app.adapters.imagery.uploaded.metadata import (
    extension_to_format,
    infer_modality,
    is_valid_jpeg_header,
    is_valid_png_header,
    is_valid_tiff_header,
    probe_raster,
    sniff_mime,
)
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.schemas.input import ImageFormat, ImageInput, ImageModality, ImageSource

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_RASTER_FORMATS = {ImageFormat.GEOTIFF, ImageFormat.TIFF}
_BENCHMARK_FORMATS = {ImageFormat.PNG, ImageFormat.JPEG}


def sanitize_filename(name: str) -> str:
    base = Path(name).name
    cleaned = _SAFE_FILENAME.sub("_", base).strip("._")
    return cleaned or "upload"


def generate_image_id() -> str:
    return uuid.uuid4().hex


def validate_file_size(file_size: int) -> None:
    settings = get_settings()
    max_bytes = settings.max_upload_size_bytes
    if file_size > max_bytes:
        raise SatQueryError(
            code="file_too_large",
            message=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
            status_code=413,
        )
    if file_size <= 0:
        raise SatQueryError(
            code="empty_file",
            message="Uploaded file is empty.",
            status_code=400,
        )


def validate_extension_and_format(
    extension: str,
    *,
    benchmark_dataset: bool,
) -> ImageFormat:
    fmt = extension_to_format(extension)
    if fmt is None:
        raise SatQueryError(
            code="unsupported_format",
            message="Unsupported file extension. Allowed: GeoTIFF, TIFF, PNG, JPEG.",
            status_code=400,
        )
    if fmt in _BENCHMARK_FORMATS and not benchmark_dataset:
        raise SatQueryError(
            code="benchmark_required",
            message="PNG/JPEG uploads require benchmark_dataset=true.",
            status_code=400,
        )
    return fmt


def validate_raster_readable(path: Path, image_format: ImageFormat) -> None:
    if image_format in _RASTER_FORMATS and not is_valid_tiff_header(path):
        raise SatQueryError(
            code="invalid_raster",
            message="File is not a readable TIFF/GeoTIFF.",
            status_code=400,
        )
    if image_format == ImageFormat.PNG and not is_valid_png_header(path):
        raise SatQueryError(
            code="invalid_raster",
            message="File is not a readable PNG.",
            status_code=400,
        )
    if image_format == ImageFormat.JPEG and not is_valid_jpeg_header(path):
        raise SatQueryError(
            code="invalid_raster",
            message="File is not a readable JPEG.",
            status_code=400,
        )


def validate_georeferencing(image_format: ImageFormat, georeferenced: bool) -> None:
    if image_format in _RASTER_FORMATS and not georeferenced:
        raise SatQueryError(
            code="missing_georeferencing",
            message="GeoTIFF/TIFF must include georeferencing tags.",
            status_code=400,
        )


def build_image_input(
    *,
    image_id: str,
    path: Path,
    original_filename: str,
    image_format: ImageFormat,
    modality: ImageModality | None,
    benchmark_dataset: bool,
    acquisition_datetime: datetime | None = None,
    co_registered_benchmark: bool = False,
    benchmark_pair_id: str | None = None,
) -> ImageInput:
    try:
        probe = probe_raster(path, image_format)
    except Exception as exc:
        raise SatQueryError(
            code="invalid_raster",
            message="Unable to read raster metadata.",
            status_code=400,
        ) from exc

    validate_georeferencing(image_format, probe.georeferenced)
    resolved_modality = infer_modality(modality, probe.band_count, image_format)

    return ImageInput(
        id=image_id,
        modality=resolved_modality,
        format=image_format,
        filename=sanitize_filename(original_filename),
        crs=probe.crs,
        width=probe.width,
        height=probe.height,
        resolution_x=probe.resolution_x,
        resolution_y=probe.resolution_y,
        bounds=probe.bounds,
        band_names=probe.band_names,
        dtype=probe.dtype,
        file_size_bytes=path.stat().st_size,
        georeferenced=probe.georeferenced,
        source=ImageSource.UPLOAD,
        benchmark_dataset=benchmark_dataset,
        acquisition_datetime=acquisition_datetime,
        co_registered_benchmark=co_registered_benchmark,
        benchmark_pair_id=benchmark_pair_id,
    )
