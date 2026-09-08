"""Remote-sensing VLM adapter boundary (Phase 10–11)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.input import ImageInput
from app.schemas.vqa import (
    GeoChatCaptionParameters,
    GeoChatVQAParameters,
    SingleImageCaptionResult,
    SingleImageVQAResult,
)


class RemoteSensingVLM(ABC):
    """Abstract GeoChat / RS-VLM inference provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def provider_kind(self) -> str:
        ...

    @abstractmethod
    async def run_vqa(
        self,
        *,
        image: ImageInput,
        question: str,
        parameters: GeoChatVQAParameters,
    ) -> SingleImageVQAResult:
        ...

    @abstractmethod
    async def run_caption(
        self,
        *,
        image: ImageInput,
        user_request: str,
        parameters: GeoChatCaptionParameters,
    ) -> SingleImageCaptionResult:
        ...

    @abstractmethod
    async def run_composite_vqa(
        self,
        *,
        composite_png: bytes,
        question: str,
        parameters: GeoChatVQAParameters,
        composite_image_id: str,
        modality: str = "optical",
    ) -> SingleImageVQAResult:
        """Run VQA on a before/after composite PNG (bytes only, no filesystem paths)."""
        ...
