"""Bi-temporal uploaded change analysis contracts (Phase 12 — SIH mandatory)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BiTemporalChangeTask(str, Enum):
    BI_TEMPORAL_CHANGE_VQA = "bi_temporal_change_vqa"


class BiTemporalChangeProviderKind(str, Enum):
    DEVELOPMENT = "development"
    UPLOADED_CVA = "uploaded_cva"


class BiTemporalSceneMetrics(BaseModel):
    """Scene-level change metrics sourced from detector output."""

    model_config = ConfigDict(extra="forbid")

    changed_pixel_count: int | None = Field(default=None, ge=0)
    total_pixel_count: int | None = Field(default=None, ge=0)
    changed_percentage: float | None = None
    area_m2: float | None = Field(default=None, ge=0)
    area_ha: float | None = Field(default=None, ge=0)
    area_km2: float | None = Field(default=None, ge=0)
    region_count: int | None = Field(default=None, ge=0)


class BiTemporalDetectorSummary(BaseModel):
    """Compact detector provenance for answers and inspector consumers."""

    model_config = ConfigDict(extra="forbid")

    detector: str
    algorithm: str | None = None
    detector_version: str | None = None
    primary_index: str | None = None
    change_direction_hint: str | None = None
    histogram_confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_kind: Literal["histogram_separability"] | None = None


class BiTemporalImageProvenance(BaseModel):
    """Safe T1/T2 provenance without filesystem paths."""

    model_config = ConfigDict(extra="forbid")

    earlier_source_ref: str | None = None
    later_source_ref: str | None = None
    earlier_filename: str | None = None
    later_filename: str | None = None
    earlier_modality: str | None = None
    later_modality: str | None = None
    earlier_band_names: list[str] | None = None
    later_band_names: list[str] | None = None
    crs: str | None = None
    coregistration_performed: bool | None = None
    positional_band_fallback_used: bool | None = None


class BiTemporalChangeResult(BaseModel):
    """Structured specialist output for uploaded bi-temporal change understanding."""

    model_config = ConfigDict(extra="forbid")

    task: Literal[BiTemporalChangeTask.BI_TEMPORAL_CHANGE_VQA] = (
        BiTemporalChangeTask.BI_TEMPORAL_CHANGE_VQA
    )
    change_summary: str = Field(min_length=1)
    question: str
    changed_region_count: int = Field(ge=0)
    change_map_available: bool = False
    detector: str
    provider: BiTemporalChangeProviderKind
    provenance: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_available: bool = False
    confidence_kind: Literal["histogram_separability"] | None = None
    earlier_image_id: str
    later_image_id: str
    earlier_acquisition: datetime
    later_acquisition: datetime
    earlier_date: date
    later_date: date
    scene_metrics: BiTemporalSceneMetrics | None = None
    detector_summary: BiTemporalDetectorSummary | None = None
    image_provenance: BiTemporalImageProvenance | None = None
    inference_metadata: dict[str, Any] = Field(default_factory=dict)


class ChangeUnderstandingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: BiTemporalChangeResult
