from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.vqa import SingleImageCaptionResult, SingleImageVQAResult
from app.schemas.bi_temporal_change import BiTemporalChangeResult
from app.schemas.imagery_policy import ImageryPolicyReport

class SensorType(str, Enum):
    SENTINEL_2 = "sentinel-2"
    SENTINEL_1 = "sentinel-1"


class DataMode(str, Enum):
    DEVELOPMENT = "development"
    EARTH_ENGINE = "earth_engine"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TraceStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class GeoJSONGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon", "Point", "LineString"]
    coordinates: list[Any]

    @field_validator("coordinates")
    @classmethod
    def coordinates_not_empty(cls, v: list[Any]) -> list[Any]:
        if not v:
            raise ValueError("geometry coordinates must not be empty")
        return v


class AOI(BaseModel):
    """Area of interest as GeoJSON geometry with optional metadata."""

    geometry: GeoJSONGeometry
    name: str | None = None
    area_km2: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_polygon(self) -> AOI:
        if self.geometry.type not in ("Polygon", "MultiPolygon"):
            raise ValueError("AOI geometry must be Polygon or MultiPolygon")
        return self


class ImageryPreferences(BaseModel):
    cloud_cover_max: float = Field(default=30.0, ge=0, le=100)
    prefer_least_cloud: bool = True


class ImageryRequest(BaseModel):
    aoi: AOI
    start_date: date
    end_date: date
    sensor: SensorType = SensorType.SENTINEL_2
    preferences: ImageryPreferences = Field(default_factory=ImageryPreferences)
    demo_mode: bool = Field(
        default=False,
        description="When true, force deterministic demonstration imagery (no Earth Engine).",
    )

    @model_validator(mode="after")
    def validate_dates(self) -> ImageryRequest:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class SpatialMetadata(BaseModel):
    crs: str = "EPSG:4326"
    bbox: list[float] = Field(description="[min_lon, min_lat, max_lon, max_lat]")
    resolution_m: float | None = None


class ImageryScene(BaseModel):
    scene_id: str
    acquisition_date: date
    cloud_cover_percent: float | None = None
    preview_url: str | None = None
    platform_id: str | None = Field(
        default=None,
        description="Provider-native image identifier for downstream analysis (e.g. EE asset path)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific scene metadata (bands, tile, path/row, etc.)",
    )


class ImageryResult(BaseModel):
    source: str
    mode: DataMode
    sensor: SensorType
    scenes: list[ImageryScene]
    spatial: SpatialMetadata
    collection_id: str | None = Field(
        default=None,
        description="Source image collection identifier (e.g. COPERNICUS/S2_SR_HARMONIZED)",
    )
    provider_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-level metadata (selection policy, project, etc.)",
    )
    message: str | None = Field(
        default=None,
        description="Human-readable note, e.g. development adapter disclaimer",
    )


class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    aoi: AOI | None = None
    earlier_date: date | None = None
    later_date: date | None = None
    sensor: SensorType = SensorType.SENTINEL_2
    preferences: ImageryPreferences = Field(default_factory=ImageryPreferences)
    image_id: str | None = Field(
        default=None,
        description="Uploaded image id for single-image VQA or scene-caption mode.",
    )
    earlier_image_id: str | None = Field(
        default=None,
        description="Earlier image id for uploaded bi-temporal change analysis.",
    )
    later_image_id: str | None = Field(
        default=None,
        description="Later image id for uploaded bi-temporal change analysis.",
    )
    optical_image_id: str | None = Field(
        default=None,
        description="Optical/multispectral image id for cross-modal analysis.",
    )
    sar_image_id: str | None = Field(
        default=None,
        description="SAR image id for cross-modal analysis.",
    )
    demo_mode: bool = Field(
        default=False,
        description="Use deterministic demonstration data instead of live Earth Engine catalog.",
    )

    @property
    def is_cross_modal_upload(self) -> bool:
        return self.optical_image_id is not None and self.sar_image_id is not None

    @property
    def is_bi_temporal_upload(self) -> bool:
        return (
            self.earlier_image_id is not None
            and self.later_image_id is not None
            and not self.is_cross_modal_upload
        )

    @property
    def is_single_image_vqa(self) -> bool:
        return (
            self.image_id is not None
            and not self.is_bi_temporal_upload
            and not self.is_cross_modal_upload
        )

    @model_validator(mode="after")
    def validate_query_dates(self) -> QueryRequest:
        if self.is_cross_modal_upload:
            if self.image_id or self.earlier_image_id or self.later_image_id:
                raise ValueError(
                    "cross-modal mode requires only optical_image_id and sar_image_id"
                )
            if self.aoi is not None or self.earlier_date is not None or self.later_date is not None:
                raise ValueError("aoi and catalog dates are not used for cross-modal upload analysis")
            return self
        if self.is_bi_temporal_upload:
            if self.image_id is not None:
                raise ValueError("image_id cannot be combined with earlier_image_id/later_image_id")
            if self.aoi is not None or self.earlier_date is not None or self.later_date is not None:
                raise ValueError(
                    "aoi and catalog dates are not used for uploaded bi-temporal change analysis"
                )
            return self
        if self.is_single_image_vqa:
            if self.earlier_image_id or self.later_image_id or self.optical_image_id or self.sar_image_id:
                raise ValueError("single-image mode requires image_id only")
            return self
        if self.earlier_image_id or self.later_image_id:
            raise ValueError("earlier_image_id and later_image_id must be provided together")
        if self.optical_image_id or self.sar_image_id:
            raise ValueError("optical_image_id and sar_image_id must be provided together")
        if self.aoi is None or self.earlier_date is None or self.later_date is None:
            raise ValueError("aoi, earlier_date, and later_date are required for catalog queries")
        if self.later_date <= self.earlier_date:
            raise ValueError("later_date must be after earlier_date")
        return self


class Metric(BaseModel):
    name: str
    value: float | int | str
    unit: str | None = None
    source: str


class EvidenceRegion(BaseModel):
    id: str
    geometry: GeoJSONGeometry
    type: str = "change"
    confidence: float = Field(ge=0, le=1)
    metrics: list[Metric] = Field(default_factory=list)
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceStep(BaseModel):
    id: str
    tool_name: str
    status: TraceStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    summary: str | None = None
    error: str | None = None
    metadata: dict[str, object] | None = None


class AnalysisResult(BaseModel):
    status: AnalysisStatus
    session_id: str
    answer: str
    confidence: float = Field(ge=0, le=1)
    confidence_available: bool = True
    metrics: list[Metric] = Field(default_factory=list)
    evidence: list[EvidenceRegion] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    mode: DataMode = DataMode.DEVELOPMENT
    demonstration_data: bool = Field(
        default=False,
        description="True when the user explicitly requested demo_mode on a catalog query.",
    )
    vqa: SingleImageVQAResult | None = None
    caption: SingleImageCaptionResult | None = None
    bi_temporal_change: BiTemporalChangeResult | None = None
    cross_modal: "CrossModalOpticalSARResult | None" = None
    imagery_policy: ImageryPolicyReport | None = None


class ChangeDetectionInput(BaseModel):
    aoi: AOI
    earlier_date: date
    later_date: date
    imagery: ImageryResult
    query_hint: str | None = Field(
        default=None,
        description="Optional natural-language hint for index selection on uploaded pairs.",
    )
    change_domain: str | None = Field(
        default=None,
        description="Phase 5B/7 change domain for catalog index routing (earth_engine path).",
    )


class ChangeDetectionOutput(BaseModel):
    regions: list[EvidenceRegion]
    raw_detection_count: int
    detector: str
    mode: DataMode
    detector_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Detector-level metadata (method, threshold, scene ids, etc.)",
    )


class FetchImageryInput(BaseModel):
    request: ImageryRequest


class FetchImageryOutput(BaseModel):
    result: ImageryResult


class GenerateEvidenceInput(BaseModel):
    query: str
    imagery: ImageryResult
    fused_regions: list[EvidenceRegion]
    fusion_metadata: dict[str, Any] = Field(default_factory=dict)


class FuseEvidenceInput(BaseModel):
    cva_detections: ChangeDetectionOutput
    semantic: SemanticAnalysisOutput | None = None
    sar_detections: ChangeDetectionOutput | None = None


class FuseEvidenceOutput(BaseModel):
    regions: list[EvidenceRegion]
    fusion_metadata: dict[str, Any] = Field(default_factory=dict)


class DetectSARChangeInput(BaseModel):
    aoi: AOI
    earlier_date: date
    later_date: date
    preferences: ImageryPreferences = Field(default_factory=ImageryPreferences)


class GenerateEvidenceOutput(BaseModel):
    regions: list[EvidenceRegion]
    metrics: list[Metric]
    confidence: float


class SemanticClaim(BaseModel):
    """Structured semantic claim produced by a SemanticAnalyzer."""

    claim_type: str
    region_id: str
    confidence: float = Field(ge=0, le=1)
    metrics: list[Metric] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticAnalysisInput(BaseModel):
    aoi: AOI
    earlier_date: date
    later_date: date
    imagery: ImageryResult
    change_regions: list[EvidenceRegion]
    analysis_profile: str


class SemanticAnalysisOutput(BaseModel):
    regions: list[EvidenceRegion]
    claims: list[SemanticClaim] = Field(default_factory=list)
    analyzer: str
    mode: DataMode
    analyzer_metadata: dict[str, Any] = Field(default_factory=dict)


from app.schemas.cross_modal import CrossModalOpticalSARResult  # noqa: E402

AnalysisResult.model_rebuild()
