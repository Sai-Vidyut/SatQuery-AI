from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail


class SatQueryError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, field: str | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field
        super().__init__(message)

    def to_response(self) -> dict[str, Any]:
        return ErrorResponse(
            error=ErrorDetail(code=self.code, message=self.message, field=self.field),
        ).model_dump()
