from fastapi import APIRouter

from app.core.responses import ApiResponse, SubmitQueryData, success
from app.schemas.domain import AnalysisResult, QueryRequest, TraceStep
from app.services.query_controller import query_controller

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/submit", response_model=ApiResponse[SubmitQueryData])
async def submit_query(request: QueryRequest) -> ApiResponse[SubmitQueryData]:
    result = await query_controller.submit(request)
    return success(SubmitQueryData(session_id=result.session_id, result=result))


@router.get("/{session_id}/trace", response_model=ApiResponse[list[TraceStep]])
async def get_trace(session_id: str) -> ApiResponse[list[TraceStep]]:
    trace = query_controller.get_trace(session_id)
    return success(trace)


@router.get("/{session_id}/result", response_model=ApiResponse[AnalysisResult])
async def get_result(session_id: str) -> ApiResponse[AnalysisResult]:
    result = query_controller.get_result(session_id)
    return success(result)
