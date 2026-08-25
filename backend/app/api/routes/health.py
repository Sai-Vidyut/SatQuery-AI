from fastapi import APIRouter

from app.core.config import get_settings
from app.core.responses import ApiResponse, HealthData, success

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[HealthData])
async def health() -> ApiResponse[HealthData]:
    settings = get_settings()
    mode = "development" if settings.imagery_provider == "development" else "production"
    return success(
        HealthData(
            status="ok",
            imagery_provider=settings.imagery_provider,
            change_detector=settings.effective_change_detector,
            sar_change_detector=settings.effective_sar_change_detector,
            semantic_analyzer=settings.semantic_analyzer,
            mode=mode,
        )
    )
