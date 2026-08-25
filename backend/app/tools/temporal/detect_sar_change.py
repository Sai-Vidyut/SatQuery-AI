from __future__ import annotations

from app.adapters.change.factory import get_change_detector
from app.adapters.imagery.factory import get_imagery_provider
from app.schemas.domain import (
    ChangeDetectionInput,
    ChangeDetectionOutput,
    DataMode,
    DetectSARChangeInput,
    FetchImageryInput,
    ImageryRequest,
    SensorType,
)
from app.tools.registry import Tool


class DetectSARChangeTool(Tool[DetectSARChangeInput, ChangeDetectionOutput]):
    name = "detect_sar_change"
    description = "Fetch Sentinel-1 imagery and detect SAR backscatter change."
    input_model = DetectSARChangeInput
    output_model = ChangeDetectionOutput

    async def execute(self, payload: DetectSARChangeInput) -> ChangeDetectionOutput:
        provider = get_imagery_provider()
        imagery_request = ImageryRequest(
            aoi=payload.aoi,
            start_date=payload.earlier_date,
            end_date=payload.later_date,
            sensor=SensorType.SENTINEL_1,
            preferences=payload.preferences,
        )
        from app.tools.imagery.fetch_imagery import FetchImageryTool

        imagery_out = await FetchImageryTool().execute(FetchImageryInput(request=imagery_request))
        if imagery_out.result.mode != DataMode.EARTH_ENGINE:
            raise ValueError("SAR change detection requires Earth Engine imagery mode.")

        detector = get_change_detector(imagery_out.result.mode, SensorType.SENTINEL_1)
        return await detector.detect(
            ChangeDetectionInput(
                aoi=payload.aoi,
                earlier_date=payload.earlier_date,
                later_date=payload.later_date,
                imagery=imagery_out.result,
            )
        )
