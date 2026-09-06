"""Phase 6 — real-data evaluation harness (separate from production detectors)."""

from evaluation.metrics import compute_region_metrics
from evaluation.models import EvaluationCase, EvaluationRecord, EvaluationType
from evaluation.runner import EvaluationRunner

__all__ = [
    "EvaluationCase",
    "EvaluationRecord",
    "EvaluationType",
    "EvaluationRunner",
    "compute_region_metrics",
]
