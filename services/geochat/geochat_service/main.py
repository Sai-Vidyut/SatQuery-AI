"""FastAPI entrypoint for the GeoChat GPU inference service."""

from __future__ import annotations

import os
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

SERVICE_CONFIG = ServiceConfig.from_env()
ENGINE = (
    FakeInferenceEngine(SERVICE_CONFIG)
    if os.environ.get("GEOCHAT_SERVICE_FAKE_ENGINE", "").lower() == "true"
    else GeoChatInferenceEngine(SERVICE_CONFIG)
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if SERVICE_CONFIG.eager_load and not isinstance(ENGINE, FakeInferenceEngine):
        try:
            ENGINE.load()
        except ModelUnavailableError:
            pass
    yield


app = FastAPI(title="GeoChat Inference Service", version=SERVICE_CONFIG.service_version, lifespan=lifespan)


def _health_status() -> GeoChatHealthResponse:
    if ENGINE.model_loaded:
        status = "ok"
    elif isinstance(ENGINE, GeoChatInferenceEngine) and ENGINE.load_error:
        status = "degraded"
    else:
        status = "degraded" if SERVICE_CONFIG.eager_load else "ok"
    return GeoChatHealthResponse(
        status=status,
        model_loaded=ENGINE.model_loaded,
        model_name=SERVICE_CONFIG.model_id,
        gpu=ENGINE.gpu_name,
        provider="geochat_service",
        service_version=SERVICE_CONFIG.service_version,
        load_strategy=ENGINE.load_strategy,
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
