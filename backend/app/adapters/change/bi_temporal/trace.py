"""Structured execution trace records for the bi-temporal upload pipeline."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from app.core.errors import SatQueryError

T = TypeVar("T")

STAGE_COMPLETED = "completed"
STAGE_FAILED = "failed"
STAGE_SKIPPED = "skipped"


def trace_stage(
    stage: str,
    *,
    status: str = STAGE_COMPLETED,
    duration_ms: float = 0.0,
    tool: str = "",
    observation: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "stage": stage,
        "status": status,
        "duration_ms": round(duration_ms, 1),
    }
    if tool:
        entry["tool"] = tool
    if observation:
        entry["observation"] = observation
    if metadata:
        entry["metadata"] = metadata
    return entry


class PipelineStageRecorder:
    """Collect structured stage records with timing and SatQuery-safe failures."""

    def __init__(self) -> None:
        self.stages: list[dict[str, Any]] = []

    def run(
        self,
        stage: str,
        tool: str,
        fn: Callable[[], T],
        *,
        observation: str = "",
        metadata: dict[str, Any] | None = None,
        failure_code: str = "change_detection_failed",
        failure_message: str | None = None,
    ) -> T:
        t0 = time.perf_counter()
        try:
            result = fn()
        except SatQueryError as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            self.stages.append(
                trace_stage(
                    stage,
                    status=STAGE_FAILED,
                    duration_ms=duration_ms,
                    tool=tool,
                    observation=exc.message,
                    metadata={
                        **(metadata or {}),
                        "error_code": exc.code,
                    },
                )
            )
            raise
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            self.stages.append(
                trace_stage(
                    stage,
                    status=STAGE_FAILED,
                    duration_ms=duration_ms,
                    tool=tool,
                    observation=failure_message or f"{stage} failed.",
                    metadata={
                        **(metadata or {}),
                        "error_code": failure_code,
                        "error_type": type(exc).__name__,
                    },
                )
            )
            raise SatQueryError(
                failure_code,
                failure_message or f"Bi-temporal change detection failed during {stage}.",
                status_code=500,
            ) from exc

        duration_ms = (time.perf_counter() - t0) * 1000
        self.stages.append(
            trace_stage(
                stage,
                status=STAGE_COMPLETED,
                duration_ms=duration_ms,
                tool=tool,
                observation=observation,
                metadata=metadata,
            )
        )
        return result

    def append(
        self,
        stage: str,
        tool: str,
        *,
        observation: str = "",
        metadata: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        self.stages.append(
            trace_stage(
                stage,
                status=STAGE_COMPLETED,
                duration_ms=duration_ms,
                tool=tool,
                observation=observation,
                metadata=metadata,
            )
        )
