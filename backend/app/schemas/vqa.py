"""Single-image VQA and scene-caption contracts (Phase 10–11 — SIH mandatory)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.input import ImageInput


class VQATask(str, Enum):
    SINGLE_IMAGE_VQA = "single_image_vqa"


class CaptionTask(str, Enum):
    SINGLE_IMAGE_CAPTION = "single_image_caption"


class VQAProviderKind(str, Enum):
    """Identifies whether inference used a real RS-VLM or a development stub."""

    DEVELOPMENT = "development"
    GEOCHAT_SERVICE = "geochat_service"


class GeoChatVQAParameters(BaseModel):
    """Permitted inference parameters exposed to the planner/controller."""

    model_config = ConfigDict(extra="forbid")

    max_new_tokens: int = Field(default=200, ge=1, le=512)
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    do_sample: bool = False


GeoChatCaptionParameters = GeoChatVQAParameters


class GeoChatVQAInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image: ImageInput
    question: str = Field(min_length=3, max_length=2000)
    parameters: GeoChatVQAParameters = Field(default_factory=GeoChatVQAParameters)


class SingleImageVQAResult(BaseModel):
    """Structured specialist output for single-image VQA."""

    model_config = ConfigDict(extra="forbid")

    task: Literal[VQATask.SINGLE_IMAGE_VQA] = VQATask.SINGLE_IMAGE_VQA
    answer: str = Field(min_length=1)
    model_name: str
    model_version: str
    provider: VQAProviderKind
    provenance: str
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Only set when the underlying model exposes calibrated confidence.",
    )
    confidence_available: bool = False
    input_image_id: str
    requested_modality: str
    inference_metadata: dict[str, Any] = Field(default_factory=dict)


class GeoChatVQAOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: SingleImageVQAResult


class GeoChatCaptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image: ImageInput
    user_request: str = Field(
        min_length=3,
        max_length=2000,
        description="Original user scene-description request (routing metadata; not a VQA question).",
    )
    parameters: GeoChatCaptionParameters = Field(default_factory=GeoChatCaptionParameters)


class SingleImageCaptionResult(BaseModel):
    """Structured specialist output for single-image scene description / captioning."""

    model_config = ConfigDict(extra="forbid")

    task: Literal[CaptionTask.SINGLE_IMAGE_CAPTION] = CaptionTask.SINGLE_IMAGE_CAPTION
    description: str = Field(min_length=1)
    model_name: str
    model_version: str
    provider: VQAProviderKind
    provenance: str
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Only set when the underlying model exposes calibrated confidence.",
    )
    confidence_available: bool = False
    input_image_id: str
    requested_modality: str
    inference_metadata: dict[str, Any] = Field(default_factory=dict)


class GeoChatCaptionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: SingleImageCaptionResult
