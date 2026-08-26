"""FastAPI entrypoint for the GeoChat GPU inference service."""

from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from geochat_service.config import ServiceConfig
from geochat_service.inference import FakeInferenceEngine, GeoChatInferenceEngine, ModelUnavailableError
from geochat_service.schemas import (
    GeoChatCaptionRequest,
    GeoChatCaptionResponse,
    GeoChatHealthResponse,
    GeoChatVQARequest,
    GeoChatVQAResponse,
)

logger = logging.getLogger("geochat_service")
logging.basicConfig(level=logging.INFO)

SERVICE_CONFIG = ServiceConfig.from_env()
ENGINE = (
    FakeInferenceEngine(SERVICE_CONFIG)
    if os.environ.get("GEOCHAT_SERVICE_FAKE_ENGINE", "").lower() == "true"
    else GeoChatInferenceEngine(SERVICE_CONFIG)
)


def _start_background_load() -> None:
    def _run() -> None:
        try:
            ENGINE.load()
        except ModelUnavailableError:
            logger.exception("[geochat] background model load failed")

    threading.Thread(target=_run, daemon=True, name="geochat-model-load").start()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if SERVICE_CONFIG.eager_load and not isinstance(ENGINE, FakeInferenceEngine):
        logger.info("[geochat] eager load enabled — starting background model load")
        _start_background_load()
    yield


app = FastAPI(title="GeoChat Inference Service", version=SERVICE_CONFIG.service_version, lifespan=lifespan)


def _health_status() -> GeoChatHealthResponse:
    startup_state = getattr(ENGINE, "startup_state", "ready")
    load_error = getattr(ENGINE, "load_error", None)

    if ENGINE.model_loaded:
        status = "ok"
    elif startup_state == "starting":
        status = "degraded"
    elif startup_state == "failed" or load_error:
        status = "error"
    else:
        status = "degraded"

    return GeoChatHealthResponse(
        status=status,
        model_loaded=ENGINE.model_loaded,
        model_name=SERVICE_CONFIG.model_id,
        gpu=ENGINE.gpu_name,
        provider="geochat_service",
        service_version=SERVICE_CONFIG.service_version,
        load_strategy=ENGINE.load_strategy,
        startup_state=startup_state,
        load_error=load_error,
    )


@app.get("/health", response_model=GeoChatHealthResponse)
async def health() -> GeoChatHealthResponse:
    return _health_status()


@app.post("/v1/vqa", response_model=GeoChatVQAResponse)
async def vqa(request: Request) -> GeoChatVQAResponse:
    try:
        payload = GeoChatVQARequest.model_validate(await request.json())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    try:
        return ENGINE.run_vqa(payload)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/caption", response_model=GeoChatCaptionResponse)
async def caption(request: Request) -> GeoChatCaptionResponse:
    try:
        payload = GeoChatCaptionRequest.model_validate(await request.json())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    try:
        return ENGINE.run_caption(payload)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def main() -> None:
    import uvicorn

    uvicorn.run(
        "geochat_service.main:app",
        host=SERVICE_CONFIG.host,
        port=SERVICE_CONFIG.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
