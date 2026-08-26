from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

from app.core.errors import SatQueryError
from app.storage.base import ImageStorage

_SAFE_ID = re.compile(r"^[a-f0-9]{32}$")
_ALLOWED_EXTENSIONS = {".tif", ".tiff", ".geotiff", ".png", ".jpg", ".jpeg"}


def normalize_extension(extension: str) -> str:
    ext = extension.lower().strip()
    if not ext.startswith("."):
        ext = f".{ext}"
    if ext == ".geotiff":
        return ".tif"
    return ext


def assert_safe_image_id(image_id: str) -> None:
    if not _SAFE_ID.match(image_id):
        raise SatQueryError(
            code="invalid_image_id",
            message="Invalid image identifier.",
            status_code=400,
        )


class LocalFilesystemStorage(ImageStorage):
    """Local filesystem storage for development and single-node deployments."""

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _object_path(self, image_id: str, extension: str) -> Path:
        assert_safe_image_id(image_id)
        ext = normalize_extension(extension)
        if ext not in _ALLOWED_EXTENSIONS and ext != ".tif":
            raise SatQueryError(
                code="unsupported_format",
                message=f"Unsupported file extension: {ext}",
                status_code=400,
            )
        path = (self._root / f"{image_id}{ext}").resolve()
        if self._root not in path.parents:
            raise SatQueryError(
                code="path_traversal",
                message="Invalid storage path.",
                status_code=400,
            )
        return path

    def save(self, image_id: str, extension: str, stream: BinaryIO) -> Path:
        path = self._object_path(image_id, extension)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as dest:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                dest.write(chunk)
        return path

    def open(self, image_id: str, extension: str) -> BinaryIO:
        path = self._object_path(image_id, extension)
        if not path.exists():
            raise SatQueryError(
                code="image_not_found",
                message="Image not found.",
                status_code=404,
            )
        return path.open("rb")

    def exists(self, image_id: str, extension: str) -> bool:
        try:
            return self._object_path(image_id, extension).exists()
        except SatQueryError:
            return False

    def delete(self, image_id: str, extension: str) -> None:
        path = self._object_path(image_id, extension)
        if path.exists():
            path.unlink()

    def path_for(self, image_id: str, extension: str) -> Path:
        path = self._object_path(image_id, extension)
        if not path.exists():
            raise SatQueryError(
                code="image_not_found",
                message="Image not found.",
                status_code=404,
            )
        return path
