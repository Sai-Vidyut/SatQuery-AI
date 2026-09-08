from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import TypeAdapter

from app.adapters.change.bi_temporal.validator import resolve_upload_path
from app.adapters.imagery.uploaded.compatibility import validate_analysis_input
from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
from app.adapters.imagery.uploaded.validation import validate_file_size
from app.core.errors import SatQueryError
from app.core.responses import ApiResponse, success
from app.services.imagery_preview import parse_bbox_wgs84, render_raster_preview_png
from app.storage.factory import get_image_storage
from app.schemas.domain import ImageryRequest, ImageryResult
from app.schemas.input import (
    AnalysisInput,
    ImageModality,
    InputValidationResult,
    UploadImageResponse,
)
from app.storage.local import normalize_extension
from app.tools.imagery.fetch_imagery import fetch_imagery

router = APIRouter(prefix="/imagery", tags=["imagery"])

_analysis_input_adapter = TypeAdapter(AnalysisInput)


@router.post("/fetch", response_model=ApiResponse[ImageryResult])
async def post_fetch_imagery(request: ImageryRequest) -> ApiResponse[ImageryResult]:
    output = await fetch_imagery(request)
    return success(output.result)


@router.post("/upload", response_model=ApiResponse[UploadImageResponse])
async def post_upload_imagery(
    file: UploadFile = File(...),
    modality: ImageModality | None = Form(default=None),
    benchmark_dataset: bool = Form(default=False),
    acquisition_datetime: str | None = Form(default=None),
    co_registered_benchmark_pair: bool = Form(default=False),
    benchmark_pair_id: str | None = Form(default=None),
) -> ApiResponse[UploadImageResponse]:
    if not file.filename:
        raise SatQueryError(
            code="missing_filename",
            message="Upload filename is required.",
            status_code=400,
        )

    extension = normalize_extension(Path(file.filename).suffix)
    provider = get_uploaded_imagery_provider()

    # Read into memory-bounded stream via spooled temp file behavior of UploadFile
    contents = await file.read()
    validate_file_size(len(contents))

    from io import BytesIO

    stream = BytesIO(contents)
    parsed_acquisition: datetime | None = None
    if acquisition_datetime:
        try:
            parsed_acquisition = datetime.fromisoformat(acquisition_datetime.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SatQueryError(
                code="invalid_acquisition_datetime",
                message="acquisition_datetime must be ISO-8601 format.",
                status_code=400,
            ) from exc
    image = provider.ingest_upload(
        stream=stream,
        original_filename=file.filename,
        extension=extension,
        modality=modality,
        benchmark_dataset=benchmark_dataset,
        acquisition_datetime=parsed_acquisition,
        co_registered_benchmark=benchmark_dataset and co_registered_benchmark_pair,
        benchmark_pair_id=benchmark_pair_id if benchmark_dataset and co_registered_benchmark_pair else None,
    )
    return success(UploadImageResponse(image=image))


@router.get("/{image_id}/preview")
async def get_uploaded_imagery_preview(
    image_id: str,
    bbox: str = Query(..., description="Crop bounds as minx,miny,maxx,maxy in WGS84 degrees"),
    max_size: int = Query(default=512, ge=64, le=2048),
) -> Response:
    provider = get_uploaded_imagery_provider()
    image = provider.get(image_id)
    bbox_wgs84 = parse_bbox_wgs84(bbox)
    storage = get_image_storage()
    path = resolve_upload_path(image, storage)
    png_bytes = render_raster_preview_png(path, bbox_wgs84=bbox_wgs84, max_size=max_size)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/{image_id}", response_model=ApiResponse[UploadImageResponse])
async def get_uploaded_imagery(image_id: str) -> ApiResponse[UploadImageResponse]:
    provider = get_uploaded_imagery_provider()
    image = provider.get(image_id)
    return success(UploadImageResponse(image=image))


@router.post("/validate-input", response_model=ApiResponse[InputValidationResult])
async def post_validate_input(payload: AnalysisInput) -> ApiResponse[InputValidationResult]:
    parsed = _analysis_input_adapter.validate_python(payload)
    result = validate_analysis_input(parsed)
    return success(result)
