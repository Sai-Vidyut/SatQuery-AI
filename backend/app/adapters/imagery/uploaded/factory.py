from __future__ import annotations

from functools import lru_cache

from app.adapters.imagery.uploaded.provider import UploadedImageryProvider
from app.storage.factory import get_image_storage, get_metadata_registry


@lru_cache
def get_uploaded_imagery_provider() -> UploadedImageryProvider:
    return UploadedImageryProvider(
        storage=get_image_storage(),
        registry=get_metadata_registry(),
    )
