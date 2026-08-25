from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    aoi: AOI
    earlier_date: date
    later_date: date
    sensor: SensorType = SensorType.SENTINEL_2
    preferences: ImageryPreferences = Field(default_factory=ImageryPreferences)

    @model_validator(mode="after")
    def validate_query_dates(self) -> QueryRequest:
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
    metrics: list[Metric] = Field(default_factory=list)
    evidence: list[EvidenceRegion] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    mode: DataMode = DataMode.DEVELOPMENT


class ChangeDetectionInput(BaseModel):
    aoi: AOI
    earlier_date: date
    later_date: date
    imagery: ImageryResult


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
