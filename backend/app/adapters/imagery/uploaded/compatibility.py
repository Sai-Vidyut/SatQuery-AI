from __future__ import annotations

from app.schemas.input import (
    AnalysisInputType,
    BiTemporalAnalysisInput,
    ImageInput,
    ImageModality,
    InputCheckStatus,
    InputValidationCheck,
    InputValidationResult,
    OpticalSARPairAnalysisInput,
    PlannerInputContext,
    SingleImageAnalysisInput,
)
from app.storage.factory import get_metadata_registry

_DIM_TOLERANCE = 0.05  # 5% relative dimension mismatch tolerance
_MIN_OVERLAP_FRACTION = 0.5


def _overlap_fraction(a: list[float], b: list[float]) -> float:
    """Approximate geographic overlap fraction between two bboxes."""
    a_west, a_south, a_east, a_north = a
    b_west, b_south, b_east, b_north = b
    inter_west = max(a_west, b_west)
    inter_south = max(a_south, b_south)
    inter_east = min(a_east, b_east)
    inter_north = min(a_north, b_north)
    if inter_east <= inter_west or inter_north <= inter_south:
        return 0.0
    inter_area = (inter_east - inter_west) * (inter_north - inter_south)
    a_area = max((a_east - a_west) * (a_north - a_south), 1e-12)
    b_area = max((b_east - b_west) * (b_north - b_south), 1e-12)
    return inter_area / min(a_area, b_area)


def _dimensions_compatible(a: ImageInput, b: ImageInput) -> tuple[bool, str]:
    w_ratio = abs(a.width - b.width) / max(a.width, b.width)
    h_ratio = abs(a.height - b.height) / max(a.height, b.height)
    if w_ratio > _DIM_TOLERANCE or h_ratio > _DIM_TOLERANCE:
        return False, (
            f"Dimension mismatch: {a.width}x{a.height} vs {b.width}x{b.height} "
            f"(tolerance {_DIM_TOLERANCE:.0%})"
        )
    return True, "Dimensions are within tolerance"


def _resolve_image(image: ImageInput) -> ImageInput:
    registry = get_metadata_registry()
    if registry.exists(image.id):
        return registry.get(image.id)
    return image


def validate_single_image(image: ImageInput) -> InputValidationResult:
    image = _resolve_image(image)
    checks: list[InputValidationCheck] = []
    errors: list[str] = []
    warnings: list[str] = []

    checks.append(
        InputValidationCheck(
            check="readable",
            status=InputCheckStatus.PASS,
            message="Image metadata is present.",
        )
    )

    if image.format.value in {"png", "jpeg"} and not image.benchmark_dataset:
        checks.append(
            InputValidationCheck(
                check="benchmark_dataset",
                status=InputCheckStatus.FAIL,
                message="PNG/JPEG requires benchmark_dataset flag.",
            )
        )
        errors.append("PNG/JPEG inputs must be marked as benchmark datasets.")

    if image.georeferenced:
        checks.append(
            InputValidationCheck(
                check="georeferencing",
                status=InputCheckStatus.PASS,
                message="Image is georeferenced.",
            )
        )
    elif image.format.value in {"geotiff", "tiff"}:
        checks.append(
            InputValidationCheck(
                check="georeferencing",
                status=InputCheckStatus.FAIL,
                message="GeoTIFF/TIFF must be georeferenced.",
            )
        )
        errors.append("Missing georeferencing.")

    normalized = SingleImageAnalysisInput(image=image)
    return InputValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        detected_input_type=AnalysisInputType.SINGLE_IMAGE,
        normalized_inputs=normalized,
        checks=checks,
    )


def validate_bi_temporal(
    earlier: ImageInput,
    later: ImageInput,
    *,
    require_acquisition_dates: bool = False,
) -> InputValidationResult:
    earlier_single = validate_single_image(earlier)
    later_single = validate_single_image(later)
    checks: list[InputValidationCheck] = list(earlier_single.checks) + list(later_single.checks)
    errors: list[str] = list(earlier_single.errors) + list(later_single.errors)
    warnings: list[str] = list(earlier_single.warnings) + list(later_single.warnings)
    if not earlier_single.valid or not later_single.valid:
        return InputValidationResult(
            valid=False,
            errors=errors,
            warnings=warnings,
            detected_input_type=AnalysisInputType.BI_TEMPORAL,
            checks=checks,
        )

    earlier = _resolve_image(earlier)
    later = _resolve_image(later)

    if earlier.modality == ImageModality.SAR or later.modality == ImageModality.SAR:
        checks.append(
            InputValidationCheck(
                check="modality",
                status=InputCheckStatus.FAIL,
                message="Bi-temporal pair requires optical/multispectral images.",
            )
        )
        errors.append("SAR is not valid for bi-temporal optical analysis.")

    dim_ok, dim_msg = _dimensions_compatible(earlier, later)
    checks.append(
        InputValidationCheck(
            check="dimension_compatibility",
            status=InputCheckStatus.PASS if dim_ok else InputCheckStatus.WARN,
            message=dim_msg,
        )
    )
    if not dim_ok:
        warnings.append(dim_msg)

    if earlier.bounds and later.bounds:
        overlap = _overlap_fraction(earlier.bounds, later.bounds)
        if overlap < _MIN_OVERLAP_FRACTION:
            checks.append(
                InputValidationCheck(
                    check="spatial_overlap",
                    status=InputCheckStatus.FAIL,
                    message=f"Insufficient overlap ({overlap:.0%}).",
                )
            )
            errors.append("Images do not sufficiently overlap geographically.")
        else:
            checks.append(
                InputValidationCheck(
                    check="spatial_overlap",
                    status=InputCheckStatus.PASS,
                    message=f"Overlap fraction {overlap:.0%}.",
                )
            )
    else:
        checks.append(
            InputValidationCheck(
                check="spatial_overlap",
                status=InputCheckStatus.WARN,
                message="Bounds unavailable; overlap not verified.",
            )
        )
        warnings.append("Spatial overlap could not be verified (missing bounds).")

    if earlier.crs and later.crs:
        if earlier.crs != later.crs:
            checks.append(
                InputValidationCheck(
                    check="crs_compatibility",
                    status=InputCheckStatus.WARN,
                    message=f"CRS differs: {earlier.crs} vs {later.crs}.",
                )
            )
            warnings.append("CRS mismatch between images.")
        else:
            checks.append(
                InputValidationCheck(
                    check="crs_compatibility",
                    status=InputCheckStatus.PASS,
                    message=f"Both images use {earlier.crs}.",
                )
            )

    if require_acquisition_dates:
        if not earlier.acquisition_datetime or not later.acquisition_datetime:
            checks.append(
                InputValidationCheck(
                    check="acquisition_datetime",
                    status=InputCheckStatus.FAIL,
                    message="Both images must include acquisition_datetime.",
                )
            )
            errors.append("Both images must include acquisition dates/times.")
        elif earlier.acquisition_datetime == later.acquisition_datetime:
            checks.append(
                InputValidationCheck(
                    check="acquisition_datetime",
                    status=InputCheckStatus.FAIL,
                    message="Acquisition datetimes must differ.",
                )
            )
            errors.append("Earlier and later images cannot share the same acquisition datetime.")

    if earlier.acquisition_datetime and later.acquisition_datetime:
        if later.acquisition_datetime <= earlier.acquisition_datetime:
            checks.append(
                InputValidationCheck(
                    check="temporal_ordering",
                    status=InputCheckStatus.FAIL,
                    message="Later image must be after earlier image.",
                )
            )
            errors.append("Invalid temporal ordering.")

    normalized = BiTemporalAnalysisInput(earlier=earlier, later=later)
    return InputValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        detected_input_type=AnalysisInputType.BI_TEMPORAL,
        normalized_inputs=BiTemporalAnalysisInput(
            earlier=earlier,
            later=later,
        ),
        checks=checks,
    )


def resolve_co_registration_status(optical: ImageInput, sar: ImageInput):
    from app.schemas.cross_modal import CoRegistrationStatus

    if (
        optical.co_registered_benchmark
        and sar.co_registered_benchmark
        and optical.benchmark_pair_id
        and sar.benchmark_pair_id
        and optical.benchmark_pair_id == sar.benchmark_pair_id
    ):
        return (
            CoRegistrationStatus.VERIFIED_BENCHMARK,
            f"Benchmark pair token {optical.benchmark_pair_id} (server-audited benchmark upload).",
        )
    if optical.bounds and sar.bounds:
        return (
            CoRegistrationStatus.OVERLAP_ONLY_NOT_VERIFIED,
            "Spatial overlap verified; co-registration is not proven from metadata.",
        )
    return (
        CoRegistrationStatus.UNKNOWN,
        "Insufficient metadata to assess co-registration or overlap.",
    )


def validate_optical_sar_pair(optical: ImageInput, sar: ImageInput) -> InputValidationResult:
    optical_single = validate_single_image(optical)
    sar_single = validate_single_image(sar)
    checks: list[InputValidationCheck] = list(optical_single.checks) + list(sar_single.checks)
    errors: list[str] = list(optical_single.errors) + list(sar_single.errors)
    warnings: list[str] = list(optical_single.warnings) + list(sar_single.warnings)
    if not optical_single.valid or not sar_single.valid:
        return InputValidationResult(
            valid=False,
            errors=errors,
            warnings=warnings,
            detected_input_type=AnalysisInputType.OPTICAL_SAR_PAIR,
            checks=checks,
        )

    optical = _resolve_image(optical)
    sar = _resolve_image(sar)

    if optical.modality not in (ImageModality.OPTICAL, ImageModality.MULTISPECTRAL):
        checks.append(
            InputValidationCheck(
                check="optical_modality",
                status=InputCheckStatus.FAIL,
                message="Optical slot must be optical or multispectral.",
            )
        )
        errors.append("Invalid optical image modality.")
    if sar.modality != ImageModality.SAR:
        checks.append(
            InputValidationCheck(
                check="sar_modality",
                status=InputCheckStatus.FAIL,
                message="SAR slot must be SAR modality.",
            )
        )
        errors.append("Invalid SAR image modality.")

    dim_ok, dim_msg = _dimensions_compatible(optical, sar)
    checks.append(
        InputValidationCheck(
            check="dimension_compatibility",
            status=InputCheckStatus.PASS if dim_ok else InputCheckStatus.WARN,
            message=dim_msg,
        )
    )
    if not dim_ok:
        warnings.append(dim_msg)

    if optical.bounds and sar.bounds:
        overlap = _overlap_fraction(optical.bounds, sar.bounds)
        if overlap < _MIN_OVERLAP_FRACTION:
            checks.append(
                InputValidationCheck(
                    check="spatial_overlap",
                    status=InputCheckStatus.FAIL,
                    message=f"Insufficient overlap ({overlap:.0%}).",
                )
            )
            errors.append("Optical and SAR images do not sufficiently overlap.")
        else:
            checks.append(
                InputValidationCheck(
                    check="spatial_overlap",
                    status=InputCheckStatus.PASS,
                    message=f"Overlap fraction {overlap:.0%}.",
                )
            )
            warnings.append(
                "Spatial overlap detected; co-registration is not verified unless benchmark pair token matches."
            )
    else:
        checks.append(
            InputValidationCheck(
                check="spatial_overlap",
                status=InputCheckStatus.WARN,
                message="Bounds unavailable; overlap not verified.",
            )
        )
        warnings.append("Spatial overlap could not be verified (missing bounds).")

    coreg_status, coreg_msg = resolve_co_registration_status(optical, sar)
    if coreg_status.value == "verified_benchmark":
        checks.append(
            InputValidationCheck(
                check="coregistration",
                status=InputCheckStatus.PASS,
                message=coreg_msg,
            )
        )
    else:
        checks.append(
            InputValidationCheck(
                check="coregistration",
                status=InputCheckStatus.WARN,
                message=coreg_msg,
            )
        )
        warnings.append(coreg_msg)

    normalized = OpticalSARPairAnalysisInput(optical=optical, sar=sar)
    return InputValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        detected_input_type=AnalysisInputType.OPTICAL_SAR_PAIR,
        normalized_inputs=normalized,
        checks=checks,
    )


def validate_analysis_input(
    payload: SingleImageAnalysisInput | BiTemporalAnalysisInput | OpticalSARPairAnalysisInput,
) -> InputValidationResult:
    if isinstance(payload, SingleImageAnalysisInput):
        return validate_single_image(payload.image)
    if isinstance(payload, BiTemporalAnalysisInput):
        return validate_bi_temporal(payload.earlier, payload.later)
    return validate_optical_sar_pair(payload.optical, payload.sar)


def planner_context_from_input(
    payload: SingleImageAnalysisInput | BiTemporalAnalysisInput | OpticalSARPairAnalysisInput,
) -> PlannerInputContext:
    if isinstance(payload, SingleImageAnalysisInput):
        return PlannerInputContext(
            input_type=AnalysisInputType.SINGLE_IMAGE,
            modalities=[payload.image.modality],
            available_tools=["geochat_vqa"],
        )
    if isinstance(payload, BiTemporalAnalysisInput):
        return PlannerInputContext(
            input_type=AnalysisInputType.BI_TEMPORAL,
            modalities=[payload.earlier.modality, payload.later.modality],
            available_tools=["detect_change", "change_understanding", "generate_evidence"],
        )
    return PlannerInputContext(
        input_type=AnalysisInputType.OPTICAL_SAR_PAIR,
        modalities=[payload.optical.modality, payload.sar.modality],
        available_tools=[
            "optical_analysis",
            "sar_analysis",
            "cross_modal_fusion",
            "generate_evidence",
        ],
    )
