from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.schemas.input import ImageInput
from app.storage.base import ImageStorage
from app.storage.local import LocalFilesystemStorage, assert_safe_image_id


class ImageMetadataRegistry:
    """Persists ImageInput metadata sidecars keyed by image id."""

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _meta_path(self, image_id: str) -> Path:
        assert_safe_image_id(image_id)
        path = (self._root / f"{image_id}.json").resolve()
        if self._root not in path.parents:
            raise SatQueryError(code="path_traversal", message="Invalid registry path.", status_code=400)
        return path

    def save(self, image: ImageInput) -> None:
        path = self._meta_path(image.id)
        path.write_text(image.model_dump_json(indent=2), encoding="utf-8")

    def get(self, image_id: str) -> ImageInput:
        path = self._meta_path(image_id)
        if not path.exists():
            raise SatQueryError(
                code="image_not_found",
                message="Image metadata not found.",
                status_code=404,
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return ImageInput.model_validate(data)

    def exists(self, image_id: str) -> bool:
        try:
            return self._meta_path(image_id).exists()
        except SatQueryError:
            return False

    def delete(self, image_id: str) -> None:
        path = self._meta_path(image_id)
        if path.exists():
            path.unlink()


@lru_cache
def get_image_storage() -> ImageStorage:
    settings = get_settings()
    return LocalFilesystemStorage(settings.upload_dir_path)


@lru_cache
def get_metadata_registry() -> ImageMetadataRegistry:
    settings = get_settings()
    return ImageMetadataRegistry(settings.upload_dir_path / "metadata")
