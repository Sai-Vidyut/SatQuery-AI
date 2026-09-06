from __future__ import annotations

import asyncio
import re
from pathlib import Path

from app.adapters.change.base import ChangeDetector
from app.adapters.change.bi_temporal.errors import BiTemporalPipelineError
from app.adapters.change.bi_temporal.pipeline import BiTemporalPipeline
from app.adapters.change.bi_temporal.validator import resolve_upload_path
from app.core.errors import SatQueryError
from app.schemas.domain import ChangeDetectionInput, ChangeDetectionOutput, DataMode
from app.schemas.input import ImageFormat, ImageInput
from app.storage.factory import get_image_storage, get_metadata_registry

_UPLOAD_ID_RE = re.compile(r"^upload://([a-f0-9]{32})$")


def _parse_upload_platform_id(platform_id: str) -> str:
    match = _UPLOAD_ID_RE.match(platform_id or "")
    if not match:
        raise SatQueryError(
            "invalid_imagery_metadata",
            f"Expected upload:// platform_id, got {platform_id!r}.",
            status_code=400,
        )
    return match.group(1)


def _resolve_image_inputs(payload: ChangeDetectionInput) -> tuple[ImageInput, ImageInput, str]:
    if len(payload.imagery.scenes) < 2:
        raise SatQueryError(
            "insufficient_imagery",
            "Bi-temporal change detection requires two uploaded scenes.",
            status_code=400,
        )
    registry = get_metadata_registry()
    earlier_scene = payload.imagery.scenes[0]
    later_scene = payload.imagery.scenes[-1]
    earlier_id = _parse_upload_platform_id(earlier_scene.platform_id or "")
    later_id = _parse_upload_platform_id(later_scene.platform_id or "")
    earlier = registry.get(earlier_id)
    later = registry.get(later_id)

    query_hint = ""
    for scene in payload.imagery.scenes[:2]:
        hint = (scene.metadata or {}).get("query_hint")
        if isinstance(hint, str) and hint.strip():
            query_hint = hint.strip()
            break
    return earlier, later, query_hint


class UploadedBiTemporalChangeDetector(ChangeDetector):
    """Real bi-temporal change detection on uploaded GeoTIFF pairs."""

    def __init__(self, pipeline: BiTemporalPipeline | None = None) -> None:
        self._pipeline = pipeline or BiTemporalPipeline()

    @property
    def name(self) -> str:
        return "uploaded_bi_temporal"

    async def detect(self, payload: ChangeDetectionInput) -> ChangeDetectionOutput:
        return await asyncio.to_thread(self._detect_sync, payload)

    def _detect_sync(self, payload: ChangeDetectionInput) -> ChangeDetectionOutput:
        earlier_meta, later_meta, query_hint = _resolve_image_inputs(payload)
        storage = get_image_storage()
        earlier_path = resolve_upload_path(earlier_meta, storage)
        later_path = resolve_upload_path(later_meta, storage)

        try:
            result = self._pipeline.run(
                earlier_path,
                later_path,
                earlier_meta,
                later_meta,
                query_hint=query_hint or payload.query_hint or "",
            )
        except BiTemporalPipelineError:
            raise
        except SatQueryError:
            raise
        except Exception as exc:
            raise SatQueryError(
                "change_detection_failed",
                "Uploaded bi-temporal change detection failed.",
                status_code=500,
            ) from exc

        return ChangeDetectionOutput(
            regions=result.regions,
            raw_detection_count=len(result.regions),
            detector=self.name,
            mode=DataMode.DEVELOPMENT,
            detector_metadata=result.detector_metadata,
        )
