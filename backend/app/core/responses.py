from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.schemas.domain import AnalysisResult

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T


class HealthData(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    imagery_provider: str
    change_detector: str = "development"
    sar_change_detector: str = "development"
    semantic_analyzer: str = "development"
    mode: str = Field(description="production | development")


class SubmitQueryData(BaseModel):
    session_id: str
    result: AnalysisResult


def success(data: T) -> ApiResponse[T]:
    return ApiResponse(data=data)
