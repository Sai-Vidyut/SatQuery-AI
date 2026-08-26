"""Cross-modal optical + SAR analysis contracts (Phase 13 — SIH mandatory)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.domain import EvidenceRegion


class CrossModalTask(str, Enum):
    CROSS_MODAL_OPTICAL_SAR = "cross_modal_optical_sar"


class CoRegistrationStatus(str, Enum):
    VERIFIED_BENCHMARK = "verified_benchmark"
    OVERLAP_ONLY_NOT_VERIFIED = "overlap_only_not_verified"
    UNKNOWN = "unknown"


class CrossModalProviderKind(str, Enum):
    DEVELOPMENT = "development"


class ModalityAnalysisSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modality: str
    summary: str
    analyzer: str
    provider: CrossModalProviderKind
    regions: list[EvidenceRegion] = Field(default_factory=list)
    confidence_available: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrossModalFusionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    fusion_policy: str
    fused_region_count: int = Field(ge=0)
    complementary_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrossModalOpticalSARResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: Literal[CrossModalTask.CROSS_MODAL_OPTICAL_SAR] = CrossModalTask.CROSS_MODAL_OPTICAL_SAR
    answer: str = Field(min_length=1)
    question: str
    optical_analysis: ModalityAnalysisSummary
    sar_analysis: ModalityAnalysisSummary
    fused_analysis: CrossModalFusionSummary
    co_registration_status: CoRegistrationStatus
    co_registration_provenance: str
    optical_image_id: str
    sar_image_id: str
    provider: CrossModalProviderKind
    provenance: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_available: bool = False
    inference_metadata: dict[str, Any] = Field(default_factory=dict)


class OpticalAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    optical_image_id: str
    bounds: list[float]


class SARAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    sar_image_id: str
    bounds: list[float]


class CrossModalFusionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    optical: ModalityAnalysisSummary
    sar: ModalityAnalysisSummary
    optical_image_id: str
    sar_image_id: str
    bounds: list[float]
    co_registration_status: CoRegistrationStatus
