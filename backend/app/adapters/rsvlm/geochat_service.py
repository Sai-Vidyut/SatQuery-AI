"""HTTP client for a remote GeoChat GPU inference service (Phase 9B reference environment)."""

from __future__ import annotations

import base64
from time import perf_counter

import httpx

from app.adapters.rsvlm.base import RemoteSensingVLM
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.schemas.geochat_service import (
    GeoChatCaptionRequest,
    GeoChatImageBytes,
    GeoChatImageMetadata,
    GeoChatInferenceParameters,
    GeoChatVQARequest,
)
from app.schemas.input import ImageFormat, ImageInput
from app.schemas.vqa import (
    CaptionTask,
    GeoChatCaptionParameters,
    GeoChatVQAParameters,
    SingleImageCaptionResult,
    SingleImageVQAResult,
    VQAProviderKind,
    VQATask,
)
from app.storage.factory import get_image_storage
from app.storage.local import normalize_extension


def _extension_for_image(image: ImageInput) -> str:
    mapping = {
        ImageFormat.GEOTIFF: ".tif",
        ImageFormat.TIFF: ".tif",
        ImageFormat.PNG: ".png",
        ImageFormat.JPEG: ".jpeg",
    }
    return normalize_extension(mapping[image.format].lstrip("."))


def _read_image_bytes(image: ImageInput) -> bytes:
    storage = get_image_storage()
    ext = _extension_for_image(image)
    if not storage.exists(image.id, ext):
        raise SatQueryError(
            "image_not_found",
            "Uploaded image binary not found for GeoChat service.",
            status_code=404,
        )
    with storage.open(image.id, ext) as handle:
        return handle.read()


def _image_bytes_payload(image: ImageInput, raw: bytes) -> GeoChatImageBytes:
    return GeoChatImageBytes(
        content_base64=base64.b64encode(raw).decode("ascii"),
        format=image.format.value,  # type: ignore[arg-type]
        filename=image.filename,
    )


def _image_metadata_payload(image: ImageInput) -> GeoChatImageMetadata:
    return GeoChatImageMetadata(
        image_id=image.id,
        modality=image.modality.value,
        width=image.width,
        height=image.height,
        georeferenced=image.georeferenced,
        acquisition_datetime=(
            image.acquisition_datetime.isoformat() if image.acquisition_datetime else None
        ),
        crs=image.crs,
        bounds=image.bounds,
        benchmark_dataset=image.benchmark_dataset,
    )


def _parameters_payload(
    parameters: GeoChatVQAParameters | GeoChatCaptionParameters,
) -> GeoChatInferenceParameters:
    return GeoChatInferenceParameters(
        max_new_tokens=parameters.max_new_tokens,
        temperature=parameters.temperature,
        do_sample=parameters.do_sample,
    )


def _provenance_text(body: dict) -> str:
    provenance = body.get("provenance")
    if isinstance(provenance, dict):
        model_name = provenance.get("model_name", body.get("model_name", "MBZUAI/geochat-7B"))
        provider = provenance.get("provider", "geochat_service")
        version = provenance.get("service_version")
        if version:
            return f"{model_name} via {provider} (service v{version})"
        return f"{model_name} via {provider}"
    if provenance:
        return str(provenance)
    return f"{body.get('model_name', 'MBZUAI/geochat-7B')} via geochat_service"


class GeoChatServiceVLM(RemoteSensingVLM):
    """Delegates inference to an external GPU service hosting GeoChat-7B."""

    name = "geochat_service_rsvlm"
    provider_kind = VQAProviderKind.GEOCHAT_SERVICE.value

    def __init__(self, base_url: str, model_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_id = model_id

    async def _post(self, path: str, payload: dict) -> dict:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=settings.geochat_service_timeout_s) as client:
                response = await client.post(f"{self._base_url}{path}", json=payload)
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict):
                    raise SatQueryError(
                        "geochat_malformed_response",
                        "GeoChat inference service returned a malformed JSON object.",
                        status_code=502,
                    )
                return body
        except httpx.TimeoutException as exc:
            raise SatQueryError(
                "geochat_service_timeout",
                f"GeoChat inference service timed out after {settings.geochat_service_timeout_s}s.",
                status_code=504,
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500] if exc.response is not None else str(exc)
            raise SatQueryError(
                "geochat_service_error",
                f"GeoChat inference service returned HTTP {exc.response.status_code}: {detail}",
                status_code=502,
            ) from exc
        except httpx.HTTPError as exc:
            raise SatQueryError(
                "geochat_service_error",
                f"GeoChat inference service request failed: {exc}",
                status_code=502,
            ) from exc

    async def run_vqa(
        self,
        *,
        image: ImageInput,
        question: str,
        parameters: GeoChatVQAParameters,
    ) -> SingleImageVQAResult:
        raw = _read_image_bytes(image)
        request = GeoChatVQARequest(
            model_id=self._model_id,
            question=question,
            image=_image_bytes_payload(image, raw),
            image_metadata=_image_metadata_payload(image),
            parameters=_parameters_payload(parameters),
        )
        t0 = perf_counter()
        body = await self._post("/v1/vqa", request.model_dump())
        answer = str(body.get("answer", "")).strip()
        if not answer:
            raise SatQueryError(
                "geochat_malformed_response",
                "GeoChat inference service returned an empty or missing answer.",
                status_code=502,
            )
        runtime_ms = int((perf_counter() - t0) * 1000) or int(body.get("runtime_ms", 1))
        confidence = body.get("confidence")
        confidence_available = bool(body.get("confidence_available", confidence is not None))
        provenance = _provenance_text(body)
        inference_metadata = {
            "service_url": self._base_url,
            "runtime_ms": runtime_ms,
            **(body.get("inference_metadata") or {}),
        }
        if isinstance(body.get("provenance"), dict):
            inference_metadata["service_provenance"] = body["provenance"]
        return SingleImageVQAResult(
            task=VQATask.SINGLE_IMAGE_VQA,
            answer=answer,
            model_name=str(body.get("model_name", self._model_id)),
            model_version=str(body.get("model_version", "unknown")),
            provider=VQAProviderKind.GEOCHAT_SERVICE,
            provenance=provenance,
            confidence=float(confidence) if confidence_available and confidence is not None else None,
            confidence_available=confidence_available,
            input_image_id=image.id,
            requested_modality=image.modality.value,
            inference_metadata=inference_metadata,
        )

    async def run_caption(
        self,
        *,
        image: ImageInput,
        user_request: str,
        parameters: GeoChatCaptionParameters,
    ) -> SingleImageCaptionResult:
        raw = _read_image_bytes(image)
        request = GeoChatCaptionRequest(
            model_id=self._model_id,
            user_request=user_request,
            image=_image_bytes_payload(image, raw),
            image_metadata=_image_metadata_payload(image),
            parameters=_parameters_payload(parameters),
            mode="scene_description",
        )
        t0 = perf_counter()
        body = await self._post("/v1/caption", request.model_dump())
        description = str(body.get("description", body.get("caption", ""))).strip()
        if not description:
            raise SatQueryError(
                "geochat_service_error",
                "GeoChat inference service returned an empty scene description.",
                status_code=502,
            )
        runtime_ms = int((perf_counter() - t0) * 1000) or int(body.get("runtime_ms", 1))
        confidence = body.get("confidence")
        confidence_available = bool(body.get("confidence_available", confidence is not None))
        provenance = _provenance_text(body)
        inference_metadata = {
            "service_url": self._base_url,
            "runtime_ms": runtime_ms,
            "caption_mode": "scene_description",
            **(body.get("inference_metadata") or {}),
        }
        if isinstance(body.get("provenance"), dict):
            inference_metadata["service_provenance"] = body["provenance"]
        return SingleImageCaptionResult(
            task=CaptionTask.SINGLE_IMAGE_CAPTION,
            description=description,
            model_name=str(body.get("model_name", self._model_id)),
            model_version=str(body.get("model_version", "unknown")),
            provider=VQAProviderKind.GEOCHAT_SERVICE,
            provenance=provenance,
            confidence=float(confidence) if confidence_available and confidence is not None else None,
            confidence_available=confidence_available,
            input_image_id=image.id,
            requested_modality=image.modality.value,
            inference_metadata=inference_metadata,
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
        request = GeoChatVQARequest(
            model_id=self._model_id,
            question=question,
            image=GeoChatImageBytes(
                content_base64=base64.b64encode(composite_png).decode("ascii"),
                format="png",
                filename=f"{composite_image_id}.png",
            ),
            image_metadata=GeoChatImageMetadata(
                image_id=composite_image_id,
                modality=modality,
                width=512,
                height=512,
                georeferenced=True,
                benchmark_dataset=False,
            ),
            parameters=_parameters_payload(parameters),
        )
        t0 = perf_counter()
        body = await self._post("/v1/vqa", request.model_dump())
        answer = str(body.get("answer", "")).strip()
        if not answer:
            raise SatQueryError(
                "geochat_malformed_response",
                "GeoChat inference service returned an empty or missing answer.",
                status_code=502,
            )
        runtime_ms = int((perf_counter() - t0) * 1000) or int(body.get("runtime_ms", 1))
        confidence = body.get("confidence")
        confidence_available = bool(body.get("confidence_available", confidence is not None))
        provenance = _provenance_text(body)
        inference_metadata = {
            "service_url": self._base_url,
            "runtime_ms": runtime_ms,
            "evidence_inputs": "before_after_composite_crop",
            "composite_bytes": len(composite_png),
            **(body.get("inference_metadata") or {}),
        }
        if isinstance(body.get("provenance"), dict):
            inference_metadata["service_provenance"] = body["provenance"]
        return SingleImageVQAResult(
            task=VQATask.SINGLE_IMAGE_VQA,
            answer=answer,
            model_name=str(body.get("model_name", self._model_id)),
            model_version=str(body.get("model_version", "unknown")),
            provider=VQAProviderKind.GEOCHAT_SERVICE,
            provenance=provenance,
            confidence=float(confidence) if confidence_available and confidence is not None else None,
            confidence_available=confidence_available,
            input_image_id=composite_image_id,
            requested_modality=modality,
            inference_metadata=inference_metadata,
        )
