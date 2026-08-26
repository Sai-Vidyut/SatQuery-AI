from __future__ import annotations

from pathlib import Path

from datetime import datetime

from app.adapters.imagery.uploaded.validation import (
    build_image_input,
    generate_image_id,
    validate_extension_and_format,
    validate_file_size,
    validate_raster_readable,
)
from app.core.errors import SatQueryError
from app.schemas.input import ImageInput, ImageModality
from app.storage.base import ImageStorage
from app.storage.factory import ImageMetadataRegistry


class UploadedImageryProvider:
    """Resolves user-uploaded imagery references to validated ImageInput metadata.

    This adapter does NOT perform inference, Earth Engine access, or change detection.
    Catalog imagery continues to flow through ImageryProvider (Earth Engine / development).
    """

    name = "uploaded"

    def __init__(
        self,
        storage: ImageStorage,
        registry: ImageMetadataRegistry,
    ) -> None:
        self._storage = storage
        self._registry = registry

    def get(self, image_id: str) -> ImageInput:
        return self._registry.get(image_id)

    def exists(self, image_id: str) -> bool:
        return self._registry.exists(image_id)

    def register_from_path(
        self,
        *,
        image_id: str,
        path: Path,
        original_filename: str,
        extension: str,
        modality: ImageModality | None,
        benchmark_dataset: bool,
        acquisition_datetime: datetime | None = None,
        co_registered_benchmark: bool = False,
        benchmark_pair_id: str | None = None,
    ) -> ImageInput:
        image_format = validate_extension_and_format(extension, benchmark_dataset=benchmark_dataset)
        validate_file_size(path.stat().st_size)
        validate_raster_readable(path, image_format)
        image = build_image_input(
            image_id=image_id,
            path=path,
            original_filename=original_filename,
            image_format=image_format,
            modality=modality,
            benchmark_dataset=benchmark_dataset,
            acquisition_datetime=acquisition_datetime,
            co_registered_benchmark=co_registered_benchmark,
            benchmark_pair_id=benchmark_pair_id,
        )
        self._registry.save(image)
        return image

    def ingest_upload(
        self,
        *,
        stream,
        original_filename: str,
        extension: str,
        modality: ImageModality | None,
        benchmark_dataset: bool,
        acquisition_datetime: datetime | None = None,
        co_registered_benchmark: bool = False,
        benchmark_pair_id: str | None = None,
    ) -> ImageInput:
        validate_extension_and_format(extension, benchmark_dataset=benchmark_dataset)
        image_id = generate_image_id()
        stored_path = self._storage.save(image_id, extension, stream)
        try:
            return self.register_from_path(
                image_id=image_id,
                path=stored_path,
                original_filename=original_filename,
                extension=extension,
                modality=modality,
                benchmark_dataset=benchmark_dataset,
                acquisition_datetime=acquisition_datetime,
                co_registered_benchmark=co_registered_benchmark,
                benchmark_pair_id=benchmark_pair_id,
            )
        except SatQueryError:
            self._storage.delete(image_id, extension)
            raise
        except Exception:
            self._storage.delete(image_id, extension)
            raise SatQueryError(
                code="upload_failed",
                message="Failed to process uploaded image.",
                status_code=500,
            ) from None
