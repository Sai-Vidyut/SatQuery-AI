from fastapi import APIRouter

from app.adapters.change.factory import get_change_detector
from app.core.responses import ApiResponse, success
from app.schemas.domain import ChangeDetectionInput, ChangeDetectionOutput, ImageryRequest, QueryRequest
from app.tools.imagery.fetch_imagery import fetch_imagery

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/detect-change", response_model=ApiResponse[ChangeDetectionOutput])
async def detect_change(request: QueryRequest) -> ApiResponse[ChangeDetectionOutput]:
    imagery = await fetch_imagery(
        ImageryRequest(
            aoi=request.aoi,
            start_date=request.earlier_date,
            end_date=request.later_date,
            sensor=request.sensor,
            preferences=request.preferences,
        )
    )
    detector = get_change_detector(imagery.result.mode, imagery.result.sensor)
    output = await detector.detect(
        ChangeDetectionInput(
            aoi=request.aoi,
            earlier_date=request.earlier_date,
            later_date=request.later_date,
            imagery=imagery.result,
        )
    )
    return success(output)
