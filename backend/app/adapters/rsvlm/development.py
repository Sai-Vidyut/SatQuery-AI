"""Deterministic development VLM — explicitly NOT real GeoChat inference."""

from __future__ import annotations

import hashlib
from time import perf_counter

from app.adapters.rsvlm.base import RemoteSensingVLM
from app.schemas.input import ImageInput, ImageModality
from app.schemas.vqa import (
    GeoChatCaptionParameters,
    GeoChatVQAParameters,
    CaptionTask,
    SingleImageCaptionResult,
    SingleImageVQAResult,
    VQAProviderKind,
    VQATask,
)


class DevelopmentGeoChatVLM(RemoteSensingVLM):
    """Labeled mock specialist for local tests and CI only."""

    name = "development_geochat_rsvlm"
    provider_kind = VQAProviderKind.DEVELOPMENT.value

    async def run_vqa(
        self,
        *,
        image: ImageInput,
        question: str,
        parameters: GeoChatVQAParameters,
    ) -> SingleImageVQAResult:
        t0 = perf_counter()
        digest = hashlib.sha256(f"{image.id}:{question}".encode()).hexdigest()[:12]
        modality_label = image.modality.value
        answer = (
            f"[development mock — not MBZUAI/geochat-7B] "
            f"Mock VQA response for {modality_label} image {image.id} "
            f"({image.width}x{image.height}). Question: {question.strip()} "
            f"(ref {digest})."
        )
        runtime_ms = int((perf_counter() - t0) * 1000) or 1
        return SingleImageVQAResult(
            task=VQATask.SINGLE_IMAGE_VQA,
            answer=answer,
            model_name="development-mock-geochat",
            model_version="0.0.0-dev",
            provider=VQAProviderKind.DEVELOPMENT,
            provenance="Development mock RS-VLM — not a remote-sensing adapted model.",
            confidence=None,
            confidence_available=False,
            input_image_id=image.id,
            requested_modality=modality_label,
            inference_metadata={
                "mock": True,
                "max_new_tokens": parameters.max_new_tokens,
                "do_sample": parameters.do_sample,
                "sar_supported": image.modality == ImageModality.SAR,
            },
        )

    async def run_composite_vqa(
        self,
        *,
        composite_png: bytes,
        question: str,
        parameters: GeoChatVQAParameters,
        composite_image_id: str,
        modality: str = "optical",
    ) -> SingleImageVQAResult:
        t0 = perf_counter()
        digest = hashlib.sha256(f"{composite_image_id}:{question}".encode()).hexdigest()[:12]
        answer = (
            f"[development mock — not MBZUAI/geochat-7B] "
            f"Mock evidence-grounded interpretation for region composite {composite_image_id}. "
            f"The BEFORE (left) and AFTER (right) panels show the detected change area. "
            f"Question noted: {question.strip()[:240]} "
            f"(ref {digest})."
        )
        runtime_ms = int((perf_counter() - t0) * 1000) or 1
        return SingleImageVQAResult(
            task=VQATask.SINGLE_IMAGE_VQA,
            answer=answer,
            model_name="development-mock-geochat",
            model_version="0.0.0-dev",
            provider=VQAProviderKind.DEVELOPMENT,
            provenance="Development mock RS-VLM region interpretation — not MBZUAI/geochat-7B.",
            confidence=None,
            confidence_available=False,
            input_image_id=composite_image_id,
            requested_modality=modality,
            inference_metadata={
                "mock": True,
                "evidence_inputs": "before_after_composite_crop",
                "composite_bytes": len(composite_png),
                "runtime_ms": runtime_ms,
                "max_new_tokens": parameters.max_new_tokens,
                "do_sample": parameters.do_sample,
            },
        )

    async def run_caption(
        self,
        *,
        image: ImageInput,
        user_request: str,
        parameters: GeoChatCaptionParameters,
    ) -> SingleImageCaptionResult:
        t0 = perf_counter()
        digest = hashlib.sha256(f"caption:{image.id}:{user_request}".encode()).hexdigest()[:12]
        modality_label = image.modality.value
        description = (
            f"[development mock scene caption — not MBZUAI/geochat-7B] "
            f"Scene description for {modality_label} image {image.id} "
            f"({image.width}x{image.height}). Covers land cover, major objects, and "
            f"visible patterns. User request noted: {user_request.strip()} (ref {digest})."
        )
        runtime_ms = int((perf_counter() - t0) * 1000) or 1
        return SingleImageCaptionResult(
            task=CaptionTask.SINGLE_IMAGE_CAPTION,
            description=description,
            model_name="development-mock-geochat",
            model_version="0.0.0-dev",
            provider=VQAProviderKind.DEVELOPMENT,
            provenance="Development mock RS-VLM scene caption — not a remote-sensing adapted model.",
            confidence=None,
            confidence_available=False,
            input_image_id=image.id,
            requested_modality=modality_label,
            inference_metadata={
                "mock": True,
                "caption_mode": "scene_description",
                "max_new_tokens": parameters.max_new_tokens,
                "do_sample": parameters.do_sample,
            },
        )
