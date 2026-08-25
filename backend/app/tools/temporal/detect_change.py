from __future__ import annotations

from app.adapters.change.base import ChangeDetector
from app.adapters.change.factory import get_change_detector
from app.schemas.domain import ChangeDetectionInput, ChangeDetectionOutput
from app.tools.registry import Tool


class DetectChangeTool(Tool[ChangeDetectionInput, ChangeDetectionOutput]):
    name = "detect_change"
    description = "Detect spatial change between two dates within an AOI."
    input_model = ChangeDetectionInput
    output_model = ChangeDetectionOutput

    def __init__(self, detector: ChangeDetector | None = None) -> None:
        self._detector = detector

    async def execute(self, payload: ChangeDetectionInput) -> ChangeDetectionOutput:
        detector = self._detector or get_change_detector(
            payload.imagery.mode,
            payload.imagery.sensor,
        )
        return await detector.detect(payload)
