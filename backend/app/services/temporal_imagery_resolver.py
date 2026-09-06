"""Temporal imagery policy resolver (Phase 5A).

Evaluates whether catalog or upload imagery can support a requested product mode.
Does not fetch pixels or run detection.
"""

from __future__ import annotations

from datetime import date

from app.adapters.imagery.collections import (
    BUILDING_INSTANCE_MAX_GSD_M,
    LANDSAT_AVAILABILITY_START,
    LANDSAT_COLLECTION_ID,
    LANDSAT_GSD_M,
    LANDSAT_LE07_COLLECTION_ID,
    MAX_GSD_MISMATCH_RATIO,
    NAIP_COLLECTION_ID,
    NAIP_AVAILABILITY_END,
    NAIP_AVAILABILITY_START,
    SENTINEL2_COLLECTION_ID,
    SENTINEL2_GSD_M,
    SENTINEL2_OPERATIONAL_START,
    aoi_bbox_intersects_conus,
    landsat_available_for_date,
    naip_available_for_date,
    naip_gsd_for_date,
    nearest_naip_epoch,
    sentinel2_available_for_date,
)
from app.adapters.imagery.earth_engine.geometry import bbox_from_geometry
from app.schemas.domain import AOI
from app.schemas.imagery_policy import (
    CatalogSensorKind,
    ImageryPolicyReport,
    ImageryProductMode,
    PolicyDecision,
    TemporalImageryResolution,
    TemporalScenePolicy,
)
from app.schemas.input import ImageInput


def _effective_gsd_m(image: ImageInput) -> float | None:
    if image.resolution_x is not None and image.resolution_y is not None:
        return max(float(image.resolution_x), float(image.resolution_y))
    if image.resolution_x is not None:
        return float(image.resolution_x)
    if image.resolution_y is not None:
        return float(image.resolution_y)
    if image.bounds and image.width > 0 and image.height > 0:
        west, south, east, north = image.bounds
        lat_mid = (south + north) / 2.0
        import math

        width_m = abs(east - west) * 111_320.0 * math.cos(math.radians(lat_mid))
        height_m = abs(north - south) * 111_320.0
        gsd_x = width_m / image.width
        gsd_y = height_m / image.height
        return max(gsd_x, gsd_y)
    return None


def _gsd_mismatch_ratio(gsd_a: float, gsd_b: float) -> float:
    lo = min(gsd_a, gsd_b)
    hi = max(gsd_a, gsd_b)
    if lo <= 0:
        return float("inf")
    return hi / lo


def _landsat_collection_for_date(requested: date) -> str:
    if requested.year < 2013:
        return LANDSAT_LE07_COLLECTION_ID
    return LANDSAT_COLLECTION_ID


def _catalog_scene_policy(
    *,
    role: str,
    requested: date,
    sensor: CatalogSensorKind,
    collection_id: str | None,
    gsd_m: float,
    actual_acquisition: date | None,
    policy_note: str | None,
) -> TemporalScenePolicy:
    return TemporalScenePolicy(
        role=role,  # type: ignore[arg-type]
        requested_date=requested,
        actual_acquisition_date=actual_acquisition,
        sensor=sensor,
        collection_id=collection_id,
        gsd_m=gsd_m,
        policy_note=policy_note,
    )


def _naip_catalog_pair(
    earlier_date: date,
    later_date: date,
) -> tuple[TemporalScenePolicy, TemporalScenePolicy, list[str]]:
    earlier_actual = nearest_naip_epoch(earlier_date)
    later_actual = nearest_naip_epoch(later_date)
    note = (
        "NAIP catalog policy uses nearest nominal acquisition epoch per date; "
        "actual tile acquisition may differ from requested year."
    )
    warnings: list[str] = []
    if earlier_actual.year != earlier_date.year:
        warnings.append(
            f"T1 requested {earlier_date.isoformat()} mapped to NAIP epoch "
            f"{earlier_actual.isoformat()} (not exact year match)."
        )
    if later_actual.year != later_date.year:
        warnings.append(
            f"T2 requested {later_date.isoformat()} mapped to NAIP epoch "
            f"{later_actual.isoformat()} (not exact year match)."
        )
    earlier_gsd = naip_gsd_for_date(earlier_actual)
    later_gsd = naip_gsd_for_date(later_actual)
    earlier = _catalog_scene_policy(
        role="earlier",
        requested=earlier_date,
        sensor=CatalogSensorKind.NAIP,
        collection_id=NAIP_COLLECTION_ID,
        gsd_m=earlier_gsd,
        actual_acquisition=earlier_actual,
        policy_note=note,
    )
    later = _catalog_scene_policy(
        role="later",
        requested=later_date,
        sensor=CatalogSensorKind.NAIP,
        collection_id=NAIP_COLLECTION_ID,
        gsd_m=later_gsd,
        actual_acquisition=later_actual,
        policy_note=note,
    )
    return earlier, later, warnings


def _landsat_s2_catalog_pair(
    earlier_date: date,
    later_date: date,
) -> tuple[TemporalScenePolicy, TemporalScenePolicy, list[str]]:
    warnings: list[str] = []
    if not sentinel2_available_for_date(later_date):
        raise ValueError("sentinel2_unavailable_for_later_date")
    if sentinel2_available_for_date(earlier_date):
        earlier = _catalog_scene_policy(
            role="earlier",
            requested=earlier_date,
            sensor=CatalogSensorKind.SENTINEL_2,
            collection_id=SENTINEL2_COLLECTION_ID,
            gsd_m=SENTINEL2_GSD_M,
            actual_acquisition=earlier_date,
            policy_note="Sentinel-2 anchor scene policy (catalog metadata only).",
        )
    else:
        if not landsat_available_for_date(earlier_date):
            raise ValueError("no_historical_imagery_for_earlier_date")
        earlier = _catalog_scene_policy(
            role="earlier",
            requested=earlier_date,
            sensor=CatalogSensorKind.LANDSAT,
            collection_id=_landsat_collection_for_date(earlier_date),
            gsd_m=LANDSAT_GSD_M,
            actual_acquisition=earlier_date,
            policy_note=(
                "Landsat used for T1 because Sentinel-2 was not operational before "
                f"{SENTINEL2_OPERATIONAL_START.isoformat()}."
            ),
        )
        warnings.append(
            f"T1 ({earlier_date.isoformat()}) predates Sentinel-2; Landsat "
            f"({LANDSAT_GSD_M:g} m GSD) paired with Sentinel-2 T2."
        )
    later = _catalog_scene_policy(
        role="later",
        requested=later_date,
        sensor=CatalogSensorKind.SENTINEL_2,
        collection_id=SENTINEL2_COLLECTION_ID,
        gsd_m=SENTINEL2_GSD_M,
        actual_acquisition=later_date,
        policy_note="Sentinel-2 anchor scene policy (catalog metadata only).",
    )
    return earlier, later, warnings


def _evaluate_pair_policy(
    *,
    mode: ImageryProductMode,
    earlier: TemporalScenePolicy,
    later: TemporalScenePolicy,
    warnings: list[str],
) -> ImageryPolicyReport:
    mismatch = _gsd_mismatch_ratio(earlier.gsd_m, later.gsd_m)

    if mode == ImageryProductMode.BUILDING_INSTANCE:
        if earlier.gsd_m > BUILDING_INSTANCE_MAX_GSD_M:
            return ImageryPolicyReport(
                requested_mode=mode,
                policy_decision=PolicyDecision.UNSUPPORTED,
                reason_code="gsd_too_coarse",
                reason_message=(
                    f"T1 ground sample distance ({earlier.gsd_m:g} m) exceeds the "
                    f"{BUILDING_INSTANCE_MAX_GSD_M:g} m limit for building-instance analysis."
                ),
                earlier=earlier,
                later=later,
                warnings=warnings,
                gsd_mismatch_ratio=mismatch,
            )
        if later.gsd_m > BUILDING_INSTANCE_MAX_GSD_M:
            return ImageryPolicyReport(
                requested_mode=mode,
                policy_decision=PolicyDecision.UNSUPPORTED,
                reason_code="gsd_too_coarse",
                reason_message=(
                    f"T2 ground sample distance ({later.gsd_m:g} m) exceeds the "
                    f"{BUILDING_INSTANCE_MAX_GSD_M:g} m limit for building-instance analysis."
                ),
                earlier=earlier,
                later=later,
                warnings=warnings,
                gsd_mismatch_ratio=mismatch,
            )
        if mismatch > MAX_GSD_MISMATCH_RATIO:
            return ImageryPolicyReport(
                requested_mode=mode,
                policy_decision=PolicyDecision.UNSUPPORTED,
                reason_code="gsd_mismatch",
                reason_message=(
                    f"T1/T2 resolution mismatch ({mismatch:.1f}×) exceeds the "
                    f"{MAX_GSD_MISMATCH_RATIO:g}× limit for building-instance analysis."
                ),
                earlier=earlier,
                later=later,
                warnings=warnings,
                gsd_mismatch_ratio=mismatch,
            )
        if earlier.sensor == CatalogSensorKind.LANDSAT and later.sensor == CatalogSensorKind.SENTINEL_2:
            return ImageryPolicyReport(
                requested_mode=mode,
                policy_decision=PolicyDecision.UNSUPPORTED,
                reason_code="cross_sensor_resolution",
                reason_message=(
                    "Landsat T1 paired with Sentinel-2 T2 cannot support individual "
                    "building-instance claims."
                ),
                earlier=earlier,
                later=later,
                warnings=warnings,
                gsd_mismatch_ratio=mismatch,
            )

    return ImageryPolicyReport(
        requested_mode=mode,
        policy_decision=PolicyDecision.SUPPORTED,
        earlier=earlier,
        later=later,
        warnings=warnings,
        gsd_mismatch_ratio=mismatch,
    )


class TemporalImageryResolver:
    """Policy-only resolver for catalog and upload temporal pairs."""

    def resolve_catalog(
        self,
        aoi: AOI,
        earlier_date: date,
        later_date: date,
        mode: ImageryProductMode,
    ) -> TemporalImageryResolution:
        if later_date <= earlier_date:
            report = ImageryPolicyReport(
                requested_mode=mode,
                policy_decision=PolicyDecision.UNSUPPORTED,
                reason_code="invalid_date_range",
                reason_message="later_date must be after earlier_date.",
            )
            return TemporalImageryResolution(report=report)

        bbox = bbox_from_geometry(aoi.geometry)
        warnings: list[str] = []

        use_naip = (
            aoi_bbox_intersects_conus(bbox)
            and naip_available_for_date(earlier_date)
            and naip_available_for_date(later_date)
            and earlier_date >= NAIP_AVAILABILITY_START
            and later_date <= NAIP_AVAILABILITY_END
        )

        try:
            if use_naip and mode == ImageryProductMode.BUILDING_INSTANCE:
                earlier, later, naip_warnings = _naip_catalog_pair(earlier_date, later_date)
                warnings.extend(naip_warnings)
            else:
                if mode == ImageryProductMode.BUILDING_INSTANCE and not use_naip:
                    if not sentinel2_available_for_date(later_date):
                        report = ImageryPolicyReport(
                            requested_mode=mode,
                            policy_decision=PolicyDecision.UNSUPPORTED,
                            reason_code="sentinel2_unavailable",
                            reason_message=(
                                f"Sentinel-2 is not available for {later_date.isoformat()}. "
                                "Sentinel-2 operations began 2015-06-23."
                            ),
                        )
                        return TemporalImageryResolution(report=report)
                earlier, later, pair_warnings = _landsat_s2_catalog_pair(earlier_date, later_date)
                warnings.extend(pair_warnings)
        except ValueError as exc:
            code = str(exc)
            messages = {
                "sentinel2_unavailable_for_later_date": (
                    f"Sentinel-2 is not available for {later_date.isoformat()}."
                ),
                "no_historical_imagery_for_earlier_date": (
                    f"No catalog imagery policy path for {earlier_date.isoformat()} "
                    f"(before Landsat availability {LANDSAT_AVAILABILITY_START.isoformat()})."
                ),
            }
            report = ImageryPolicyReport(
                requested_mode=mode,
                policy_decision=PolicyDecision.UNSUPPORTED,
                reason_code=code,
                reason_message=messages.get(code, "Catalog imagery policy could not resolve T1/T2."),
            )
            return TemporalImageryResolution(report=report)

        report = _evaluate_pair_policy(
            mode=mode,
            earlier=earlier,
            later=later,
            warnings=warnings,
        )
        return TemporalImageryResolution(report=report)

    def resolve_upload_pair(
        self,
        earlier: ImageInput,
        later: ImageInput,
        mode: ImageryProductMode,
    ) -> TemporalImageryResolution:
        warnings: list[str] = []
        if not earlier.acquisition_datetime or not later.acquisition_datetime:
            report = ImageryPolicyReport(
                requested_mode=mode,
                policy_decision=PolicyDecision.UNSUPPORTED,
                reason_code="missing_acquisition_datetime",
                reason_message="Both uploads must include acquisition_datetime for temporal policy.",
            )
            return TemporalImageryResolution(report=report)

        earlier_gsd = _effective_gsd_m(earlier)
        later_gsd = _effective_gsd_m(later)
        if earlier_gsd is None or later_gsd is None:
            report = ImageryPolicyReport(
                requested_mode=mode,
                policy_decision=PolicyDecision.UNSUPPORTED,
                reason_code="unknown_gsd",
                reason_message="Cannot determine ground sample distance for uploaded pair.",
            )
            return TemporalImageryResolution(report=report)

        earlier_scene = TemporalScenePolicy(
            role="earlier",
            requested_date=earlier.acquisition_datetime.date(),
            actual_acquisition_date=earlier.acquisition_datetime.date(),
            sensor=CatalogSensorKind.UPLOADED,
            collection_id="uploaded",
            gsd_m=round(earlier_gsd, 4),
            policy_note="Uploaded imagery GSD derived from metadata or bounds.",
        )
        later_scene = TemporalScenePolicy(
            role="later",
            requested_date=later.acquisition_datetime.date(),
            actual_acquisition_date=later.acquisition_datetime.date(),
            sensor=CatalogSensorKind.UPLOADED,
            collection_id="uploaded",
            gsd_m=round(later_gsd, 4),
            policy_note="Uploaded imagery GSD derived from metadata or bounds.",
        )

        report = _evaluate_pair_policy(
            mode=mode,
            earlier=earlier_scene,
            later=later_scene,
            warnings=warnings,
        )
        return TemporalImageryResolution(report=report)
