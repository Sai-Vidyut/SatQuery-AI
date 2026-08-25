from fastapi import APIRouter

from app.core.responses import ApiResponse, success
from app.schemas.domain import ImageryRequest, ImageryResult
from app.tools.imagery.fetch_imagery import fetch_imagery

router = APIRouter(prefix="/imagery", tags=["imagery"])


@router.post("/fetch", response_model=ApiResponse[ImageryResult])
async def post_fetch_imagery(request: ImageryRequest) -> ApiResponse[ImageryResult]:
    output = await fetch_imagery(request)
    return success(output.result)
