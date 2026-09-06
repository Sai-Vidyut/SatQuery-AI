"""SatQuery-native errors for the uploaded bi-temporal pipeline."""

from __future__ import annotations

from typing import Any

from app.core.errors import SatQueryError


class BiTemporalPipelineError(SatQueryError):
    """SatQuery error carrying partial pipeline stage records when available."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        *,
        pipeline_stages: list[dict[str, Any]] | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(code, message, status_code=status_code, field=field)
        self.pipeline_stages = pipeline_stages or []


def wrap_pipeline_failure(
    exc: Exception,
    *,
    pipeline_stages: list[dict[str, Any]] | None = None,
    stage: str = "pipeline",
) -> BiTemporalPipelineError:
    if isinstance(exc, BiTemporalPipelineError):
        return exc
    if isinstance(exc, SatQueryError):
        return BiTemporalPipelineError(
            exc.code,
            exc.message,
            exc.status_code,
            pipeline_stages=pipeline_stages,
            field=exc.field,
        )
    return BiTemporalPipelineError(
        "change_detection_failed",
        f"Bi-temporal change detection failed during {stage}.",
        status_code=500,
        pipeline_stages=pipeline_stages,
    )
