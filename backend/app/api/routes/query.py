from fastapi import APIRouter

from app.core.responses import ApiResponse, SubmitQueryData, success
from app.schemas.domain import AnalysisResult, QueryRequest, TraceStep
from app.schemas.region_chat import RegionChatData, RegionChatRequest
from app.schemas.region_interpretation import InterpretRegionData, RegionInterpretationRequest
from app.services.query_controller import query_controller
from app.services.region_chat import region_chat_service
from app.services.region_interpretation import region_interpretation_service

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


@router.post(
    "/{session_id}/regions/{region_id}/interpret",
    response_model=ApiResponse[InterpretRegionData],
)
async def interpret_region(
    session_id: str,
    region_id: str,
    request: RegionInterpretationRequest,
) -> ApiResponse[InterpretRegionData]:
    interpretation, trace_step = await region_interpretation_service.interpret_region(
        session_id,
        region_id,
        request.question,
    )
    return success(
        InterpretRegionData(
            interpretation=interpretation,
            trace_step=trace_step.model_dump(mode="json"),
        )
    )


@router.post(
    "/{session_id}/regions/{region_id}/chat",
    response_model=ApiResponse[RegionChatData],
)
async def chat_region(
    session_id: str,
    region_id: str,
    request: RegionChatRequest,
) -> ApiResponse[RegionChatData]:
    chat, trace_step = await region_chat_service.chat(
        session_id,
        region_id,
        request.message,
    )
    return success(
        RegionChatData(
            chat=chat,
            trace_step=trace_step.model_dump(mode="json"),
        )
    )
