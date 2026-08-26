"""User-supplied imagery input contracts (Phase 8).

ImageInput represents uploaded/registered imagery awaiting specialist processing.
ImageryScene (domain.py) represents catalog observations returned by providers.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImageModality(str, Enum):
    OPTICAL = "optical"
    MULTISPECTRAL = "multispectral"
    SAR = "sar"


class ImageFormat(str, Enum):
    GEOTIFF = "geotiff"
    TIFF = "tiff"
    PNG = "png"
    JPEG = "jpeg"


class AnalysisInputType(str, Enum):
    SINGLE_IMAGE = "single_image"
    BI_TEMPORAL = "bi_temporal"
    OPTICAL_SAR_PAIR = "optical_sar_pair"


class ImageSource(str, Enum):
    UPLOAD = "upload"
    EARTH_ENGINE = "earth_engine"


class ImageInput(BaseModel):
    """Normalized metadata for a single user-supplied image."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Internal image identifier (never a filesystem path)")
    modality: ImageModality
    format: ImageFormat
    filename: str = Field(description="Original sanitized filename for display")
    acquisition_datetime: datetime | None = None
    crs: str | None = Field(default=None, description="EPSG code or WKT when known")
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    resolution_x: float | None = Field(default=None, description="Ground sample distance, x axis")
    resolution_y: float | None = Field(default=None, description="Ground sample distance, y axis")
    bounds: list[float] | None = Field(
        default=None,
        description="Geographic bounds [min_lon, min_lat, max_lon, max_lat]",
        min_length=4,
        max_length=4,
    )
    band_names: list[str] | None = None
    dtype: str | None = None
    file_size_bytes: int = Field(ge=0)
    georeferenced: bool = False
    source: ImageSource = ImageSource.UPLOAD
    benchmark_dataset: bool = Field(
        default=False,
        description="True when PNG/JPEG is from a prescribed benchmark/public dataset",
    )
    co_registered_benchmark: bool = Field(
        default=False,
        description="Server-set when uploaded via trusted benchmark co-registration procedure.",
    )
    benchmark_pair_id: str | None = Field(
        default=None,
        description="Auditable pair token linking co-registered benchmark uploads.",
    )


class SingleImageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image: ImageInput


class BiTemporalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    earlier: ImageInput
    later: ImageInput


class OpticalSARPairInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    optical: ImageInput
    sar: ImageInput


class SingleImageAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_type: Literal[AnalysisInputType.SINGLE_IMAGE] = AnalysisInputType.SINGLE_IMAGE
    image: ImageInput


class BiTemporalAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_type: Literal[AnalysisInputType.BI_TEMPORAL] = AnalysisInputType.BI_TEMPORAL
    earlier: ImageInput
    later: ImageInput


class OpticalSARPairAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_type: Literal[AnalysisInputType.OPTICAL_SAR_PAIR] = AnalysisInputType.OPTICAL_SAR_PAIR
    optical: ImageInput
    sar: ImageInput


AnalysisInput = Annotated[
    SingleImageAnalysisInput | BiTemporalAnalysisInput | OpticalSARPairAnalysisInput,
    Field(discriminator="input_type"),
]


class InputCheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class InputValidationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: str
    status: InputCheckStatus
    message: str


class InputValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    detected_input_type: AnalysisInputType | None = None
    normalized_inputs: (
        SingleImageAnalysisInput | BiTemporalAnalysisInput | OpticalSARPairAnalysisInput | None
    ) = None
    checks: list[InputValidationCheck] = Field(default_factory=list)


class UploadImageResponse(BaseModel):
    """API response after a successful image upload and validation."""

    model_config = ConfigDict(extra="forbid")

    image: ImageInput


class PlannerInputContext(BaseModel):
    """Typed routing context for future planner integration (no inference in Phase 8)."""

    model_config = ConfigDict(extra="forbid")

    input_type: AnalysisInputType
    modalities: list[ImageModality]
    available_tools: list[str] = Field(
        default_factory=list,
        description="Specialist tools that could apply once implemented",
    )

    @model_validator(mode="after")
    def validate_modalities(self) -> PlannerInputContext:
        if not self.modalities:
            raise ValueError("modalities must not be empty")
        return self
