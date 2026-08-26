"""Single-image VQA and caption pipeline helpers."""

from __future__ import annotations

from app.schemas.domain import Metric
from app.schemas.vqa import SingleImageCaptionResult, SingleImageVQAResult


def build_vqa_metrics(result: SingleImageVQAResult) -> list[Metric]:
    metrics = [
        Metric(
            name="vqa_provider",
            value=result.provider.value,
            source="geochat_vqa",
        ),
        Metric(
            name="vqa_model",
            value=result.model_name,
            source="geochat_vqa",
        ),
        Metric(
            name="vqa_model_version",
            value=result.model_version,
            source="geochat_vqa",
        ),
        Metric(
            name="vqa_confidence_available",
            value=str(result.confidence_available).lower(),
            source="geochat_vqa",
        ),
    ]
    if result.confidence_available and result.confidence is not None:
        metrics.append(
            Metric(
                name="vqa_confidence",
                value=result.confidence,
                source="geochat_vqa",
            )
        )
    runtime = result.inference_metadata.get("runtime_ms")
    if runtime is not None:
        metrics.append(
            Metric(
                name="vqa_runtime_ms",
                value=int(runtime),
                unit="ms",
                source="geochat_vqa",
            )
        )
    return metrics


def build_caption_metrics(result: SingleImageCaptionResult) -> list[Metric]:
    metrics = [
        Metric(
            name="caption_provider",
            value=result.provider.value,
            source="geochat_caption",
        ),
        Metric(
            name="caption_model",
            value=result.model_name,
            source="geochat_caption",
        ),
        Metric(
            name="caption_model_version",
            value=result.model_version,
            source="geochat_caption",
        ),
        Metric(
            name="caption_confidence_available",
            value=str(result.confidence_available).lower(),
            source="geochat_caption",
        ),
    ]
    if result.confidence_available and result.confidence is not None:
        metrics.append(
            Metric(
                name="caption_confidence",
                value=result.confidence,
                source="geochat_caption",
            )
        )
    runtime = result.inference_metadata.get("runtime_ms")
    if runtime is not None:
        metrics.append(
            Metric(
                name="caption_runtime_ms",
                value=int(runtime),
                unit="ms",
                source="geochat_caption",
            )
        )
    return metrics
