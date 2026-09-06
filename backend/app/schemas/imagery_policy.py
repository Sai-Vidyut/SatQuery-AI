"""Imagery policy contracts for catalog temporal analysis (Phase 5A)."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImageryProductMode(str, Enum):
    """Analysis product mode — distinct from query intent."""

    BUILT_AREA = "built_area"
    BUILDING_INSTANCE = "building_instance"


class PolicyDecision(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


class CatalogSensorKind(str, Enum):
    SENTINEL_2 = "sentinel-2"
    LANDSAT = "landsat"
    NAIP = "naip"
    UPLOADED = "uploaded"


class TemporalScenePolicy(BaseModel):
    """Per-scene policy metadata without filesystem paths."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["earlier", "later"]
    requested_date: date
    actual_acquisition_date: date | None = None
    sensor: CatalogSensorKind
    collection_id: str | None = None
    gsd_m: float = Field(gt=0)
    policy_note: str | None = None


class ImageryPolicyReport(BaseModel):
    """Outcome of temporal imagery policy evaluation."""

    model_config = ConfigDict(extra="forbid")

    requested_mode: ImageryProductMode
    policy_decision: PolicyDecision
    reason_code: str | None = None
    reason_message: str | None = None
    policy_version: str = "1.0.0"
    earlier: TemporalScenePolicy | None = None
    later: TemporalScenePolicy | None = None
    warnings: list[str] = Field(default_factory=list)
    gsd_mismatch_ratio: float | None = Field(default=None, ge=0)


class TemporalImageryResolution(BaseModel):
    """Resolver output: policy report (catalog imagery stubs are internal to resolver)."""

    model_config = ConfigDict(extra="forbid")

    report: ImageryPolicyReport
