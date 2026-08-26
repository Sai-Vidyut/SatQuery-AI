"""GeoChat-7B model loading and inference (Phase 9B T4 8-bit path)."""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from geochat_service.config import LOAD_STRATEGY, PROMPT_SYSTEM, ServiceConfig
from geochat_service.loading import load_geochat_runtime
from geochat_service.preprocessing import prepare_geochat_image
from geochat_service.schemas import (
    GeoChatCaptionRequest,
    GeoChatCaptionResponse,
    GeoChatImageBytes,
    GeoChatImageMetadata,
    GeoChatInferenceParameters,
    GeoChatServiceProvenance,
    GeoChatVQARequest,
    GeoChatVQAResponse,
)

StartupState = Literal["idle", "starting", "ready", "failed"]


class ModelUnavailableError(RuntimeError):
    """Raised when GeoChat weights cannot be loaded or CUDA is unavailable."""


class InferenceEngine(Protocol):
    model_loaded: bool
    model_name: str
    load_strategy: str | None
    gpu_name: str | None
    startup_state: StartupState
    load_error: str | None

    def load(self) -> None: ...

    def run_vqa(self, request: GeoChatVQARequest) -> GeoChatVQAResponse: ...

    def run_caption(self, request: GeoChatCaptionRequest) -> GeoChatCaptionResponse: ...


@dataclass
class GeoChatRuntime:
    model: Any
    tokenizer: Any
    image_processor: Any
    device: Any
    load_strategy: str
    gpu_name: str | None


class GeoChatInferenceEngine:
    """Loads MBZUAI/geochat-7B with verified 8-bit T4 strategy."""

    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._runtime: GeoChatRuntime | None = None
        self._load_error: str | None = None
        self._startup_state: StartupState = "idle"
        self._load_lock = threading.Lock()

    @property
    def startup_state(self) -> StartupState:
        return self._startup_state

    @property
    def model_loaded(self) -> bool:
        return self._startup_state == "ready" and self._runtime is not None

    @property
    def model_name(self) -> str:
        return self._config.model_id

    @property
    def load_strategy(self) -> str | None:
        return LOAD_STRATEGY if self.model_loaded else None

    @property
    def gpu_name(self) -> str | None:
        return self._runtime.gpu_name if self._runtime else None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def _ensure_geochat_src(self) -> Path:
        if not self._config.geochat_src:
            raise ModelUnavailableError(
                "GEOCHAT_SRC is not set. Clone https://github.com/mbzuai-oryx/GeoChat.git "
                "and point GEOCHAT_SRC at the repository root."
            )
        root = Path(self._config.geochat_src).resolve()
        if not (root / "geochat").exists():
            raise ModelUnavailableError(f"GEOCHAT_SRC does not contain geochat package: {root}")
        return root

    def load(self) -> None:
        with self._load_lock:
            if self._startup_state == "ready":
                return
            if self._startup_state == "failed":
                raise ModelUnavailableError(self._load_error or "GeoChat model load failed.")
            if self._startup_state == "starting":
                return
            self._startup_state = "starting"
            self._load_error = None

        try:
            geochat_root = self._ensure_geochat_src()
            loaded = load_geochat_runtime(
                model_id=self._config.model_id,
                geochat_src=geochat_root,
                hf_token=self._config.hf_token,
            )
            runtime = GeoChatRuntime(
                model=loaded["model"],
                tokenizer=loaded["tokenizer"],
                image_processor=loaded["image_processor"],
                device=loaded["device"],
                load_strategy=loaded["load_strategy"],
                gpu_name=loaded["gpu_name"],
            )
            with self._load_lock:
                self._runtime = runtime
                self._startup_state = "ready"
                self._load_error = None
        except Exception as exc:
            with self._load_lock:
                self._startup_state = "failed"
                self._load_error = str(exc)
                self._runtime = None
            print(f"[geochat] model load failed: {exc}", flush=True)
            raise ModelUnavailableError(str(exc)) from exc

    def _provenance(self, runtime_ms: int, device: str | None = None) -> GeoChatServiceProvenance:
        return GeoChatServiceProvenance(
            model_name=self._config.model_id,
            provider="geochat_service",
            service_version=self._config.service_version,
            runtime_ms=runtime_ms,
            load_strategy=LOAD_STRATEGY,
            inference_device=device,
        )

    def _generate(
        self,
        *,
        pil_image,
        prompt: str,
        parameters: GeoChatInferenceParameters,
        preprocess_meta: dict,
    ) -> tuple[str, dict]:
        if self._runtime is None or not self.model_loaded:
            raise ModelUnavailableError("GeoChat model is not loaded.")
        import torch
        from geochat.constants import IMAGE_TOKEN_INDEX
        from geochat.mm_utils import process_images_demo, tokenizer_image_token

        runtime = self._runtime
        image_tensor = process_images_demo([pil_image], runtime.image_processor)
        image_tensor = image_tensor.to(device=runtime.device, dtype=torch.float16)
        input_ids = (
            tokenizer_image_token(prompt, runtime.tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt")
            .unsqueeze(0)
            .to(runtime.device)
        )
        t0 = time.time()
        with torch.inference_mode():
            output_ids = runtime.model.generate(
                input_ids,
                images=image_tensor,
                do_sample=parameters.do_sample,
                temperature=parameters.temperature,
                max_new_tokens=parameters.max_new_tokens,
                use_cache=True,
            )
        runtime_ms = int((time.time() - t0) * 1000)
        answer = runtime.tokenizer.decode(
            output_ids[0, input_ids.shape[1] :], skip_special_tokens=True
        ).strip()
        if not answer:
            raise RuntimeError("GeoChat returned an empty generation.")
        inference_metadata = {
            **preprocess_meta,
            "generation_ms": runtime_ms,
            "inference_device": str(runtime.device),
        }
        return answer, inference_metadata

    def run_vqa(self, request: GeoChatVQARequest) -> GeoChatVQAResponse:
        self.load()
        if not self.model_loaded:
            raise ModelUnavailableError("GeoChat model is still loading or failed to load.")
        pil_image, preprocess_meta = prepare_geochat_image(request.image, request.image_metadata)
        prompt = f"{PROMPT_SYSTEM} USER: <image>\n{request.question} ASSISTANT:"
        t0 = time.time()
        answer, inference_metadata = self._generate(
            pil_image=pil_image,
            prompt=prompt,
            parameters=request.parameters,
            preprocess_meta=preprocess_meta,
        )
        runtime_ms = int((time.time() - t0) * 1000)
        return GeoChatVQAResponse(
            answer=answer,
            model_name=request.model_id,
            provider="geochat_service",
            confidence_available=False,
            confidence=None,
            runtime_ms=runtime_ms,
            provenance=self._provenance(runtime_ms, str(self._runtime.device if self._runtime else None)),
            inference_metadata=inference_metadata,
        )

    def run_caption(self, request: GeoChatCaptionRequest) -> GeoChatCaptionResponse:
        self.load()
        if not self.model_loaded:
            raise ModelUnavailableError("GeoChat model is still loading or failed to load.")
        pil_image, preprocess_meta = prepare_geochat_image(request.image, request.image_metadata)
        prompt = f"{PROMPT_SYSTEM} USER: <image>\n{request.user_request} ASSISTANT:"
        t0 = time.time()
        description, inference_metadata = self._generate(
            pil_image=pil_image,
            prompt=prompt,
            parameters=request.parameters,
            preprocess_meta=preprocess_meta,
        )
        runtime_ms = int((time.time() - t0) * 1000)
        inference_metadata["caption_mode"] = request.mode
        return GeoChatCaptionResponse(
            description=description,
            model_name=request.model_id,
            provider="geochat_service",
            confidence_available=False,
            confidence=None,
            runtime_ms=runtime_ms,
            provenance=self._provenance(runtime_ms, str(self._runtime.device if self._runtime else None)),
            inference_metadata=inference_metadata,
        )


class FakeInferenceEngine:
    """Deterministic engine for service unit tests — not used in production."""

    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self.model_loaded = True
        self.model_name = config.model_id
        self.load_strategy = "fake_engine"
        self.gpu_name = "fake-gpu"
        self.startup_state: StartupState = "ready"
        self.load_error: str | None = None

    def load(self) -> None:
        return None

    def run_vqa(self, request: GeoChatVQARequest) -> GeoChatVQAResponse:
        pil_image, preprocess_meta = prepare_geochat_image(request.image, request.image_metadata)
        answer = (
            f"[fake geochat service] VQA for {request.image_metadata.image_id} "
            f"({pil_image.size[0]}x{pil_image.size[1]}): {request.question.strip()}"
        )
        return GeoChatVQAResponse(
            answer=answer,
            model_name=self.model_name,
            provider="geochat_service",
            confidence_available=False,
            runtime_ms=1,
            provenance=GeoChatServiceProvenance(
                model_name=self.model_name,
                provider="geochat_service",
                service_version=self._config.service_version,
                runtime_ms=1,
                load_strategy="fake_engine",
                inference_device="fake",
            ),
            inference_metadata=preprocess_meta,
        )

    def run_caption(self, request: GeoChatCaptionRequest) -> GeoChatCaptionResponse:
        pil_image, preprocess_meta = prepare_geochat_image(request.image, request.image_metadata)
        description = (
            f"[fake geochat service] Scene description for {request.image_metadata.image_id} "
            f"({pil_image.size[0]}x{pil_image.size[1]}): {request.user_request.strip()}"
        )
        preprocess_meta["caption_mode"] = request.mode
        return GeoChatCaptionResponse(
            description=description,
            model_name=self.model_name,
            provider="geochat_service",
            confidence_available=False,
            runtime_ms=1,
            provenance=GeoChatServiceProvenance(
                model_name=self.model_name,
                provider="geochat_service",
                service_version=self._config.service_version,
                runtime_ms=1,
                load_strategy="fake_engine",
                inference_device="fake",
            ),
            inference_metadata=preprocess_meta,
        )
