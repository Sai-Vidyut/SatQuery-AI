from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import SatQueryError


@dataclass(frozen=True)
class EarthEngineClient:
    """Thin wrapper around the Earth Engine Python API for testability."""

    ee: Any
    project: str | None

    @classmethod
    def initialize(cls, settings: Settings | None = None) -> EarthEngineClient:
        settings = settings or get_settings()
        try:
            import ee  # type: ignore[import-untyped]
        except ImportError as exc:
            raise SatQueryError(
                "earth_engine_unavailable",
                "earthengine-api is not installed. Install with: pip install earthengine-api",
                status_code=503,
            ) from exc

        try:
            if settings.earth_engine_project:
                ee.Initialize(project=settings.earth_engine_project)
            else:
                ee.Initialize()
        except Exception as exc:
            raise SatQueryError(
                "earth_engine_auth_failed",
                "Earth Engine authentication failed. Run 'earthengine authenticate' "
                "or set GOOGLE_APPLICATION_CREDENTIALS. See README.md.",
                status_code=503,
            ) from exc

        return cls(ee=ee, project=settings.earth_engine_project)

    def image_collection(self, collection_id: str) -> Any:
        return self.ee.ImageCollection(collection_id)
