from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class ImageStorage(ABC):
    """Abstract storage for uploaded imagery binaries."""

    @abstractmethod
    def save(self, image_id: str, extension: str, stream: BinaryIO) -> Path:
        """Persist binary content. Returns internal storage key (not exposed to clients)."""

    @abstractmethod
    def open(self, image_id: str, extension: str) -> BinaryIO:
        """Open stored binary for reading."""

    @abstractmethod
    def exists(self, image_id: str, extension: str) -> bool:
        ...

    @abstractmethod
    def delete(self, image_id: str, extension: str) -> None:
        ...

    @abstractmethod
    def path_for(self, image_id: str, extension: str) -> Path:
        """Internal path for adapter metadata extraction (never returned via API)."""
