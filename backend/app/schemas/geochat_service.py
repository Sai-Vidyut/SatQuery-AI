"""HTTP contract between SatQuery backend and the GeoChat GPU inference service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GeoChatImageBytes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_base64: str = Field(min_length=1)
    format: Literal["geotiff", "tiff", "png", "jpeg"]
    filename: str = Field(min_length=1)


class GeoChatImageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: str
    modality: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    georeferenced: bool = False
    acquisition_datetime: str | None = None
    crs: str | None = None
    bounds: list[float] | None = None
    benchmark_dataset: bool = False


class GeoChatInferenceParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_new_tokens: int = Field(default=200, ge=1, le=512)
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    do_sample: bool = False


class GeoChatVQARequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(default="MBZUAI/geochat-7B")
    question: str = Field(min_length=1)
    image: GeoChatImageBytes
    image_metadata: GeoChatImageMetadata
    parameters: GeoChatInferenceParameters = Field(default_factory=GeoChatInferenceParameters)


class GeoChatCaptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(default="MBZUAI/geochat-7B")
    user_request: str = Field(min_length=1)
    image: GeoChatImageBytes
    image_metadata: GeoChatImageMetadata
    parameters: GeoChatInferenceParameters = Field(default_factory=GeoChatInferenceParameters)
    mode: Literal["scene_description"] = "scene_description"


class GeoChatServiceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    provider: Literal["geochat_service"] = "geochat_service"
    service_version: str
    runtime_ms: int = Field(ge=0)
    load_strategy: str | None = None
    inference_device: str | None = None


class GeoChatVQAResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    model_name: str
    provider: Literal["geochat_service"] = "geochat_service"
    confidence_available: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)
    model_version: str = "unknown"
    runtime_ms: int = Field(ge=0)
    provenance: GeoChatServiceProvenance | dict[str, Any]
    inference_metadata: dict[str, Any] = Field(default_factory=dict)


class GeoChatCaptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)
    model_name: str
    provider: Literal["geochat_service"] = "geochat_service"
    confidence_available: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)
    model_version: str = "unknown"
    runtime_ms: int = Field(ge=0)
    provenance: GeoChatServiceProvenance | dict[str, Any]
    inference_metadata: dict[str, Any] = Field(default_factory=dict)


class GeoChatHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded", "error"]
    model_loaded: bool
    model_name: str
    gpu: str | None = None
    provider: Literal["geochat_service"] = "geochat_service"
    service_version: str
    load_strategy: str | None = None
    startup_state: Literal["idle", "starting", "ready", "failed"] | None = None
    load_error: str | None = None
