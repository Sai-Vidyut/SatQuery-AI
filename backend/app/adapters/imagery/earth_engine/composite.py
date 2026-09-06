"""Multi-scene seasonal median composite policy for Sentinel-2 catalog imagery (Phase 8)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.adapters.imagery.earth_engine.seasonality import (
    SEASONALITY_POLICY_VERSION,
    build_seasonality_provenance,
    is_cross_season_pair,
)
from app.adapters.imagery.earth_engine.selection import _sort_key_distance_to
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.core.errors import SatQueryError
from app.schemas.domain import ImageryScene

COMPOSITE_POLICY_VERSION = "2.1.0"
FALLBACK_POLICY_VERSION = "1.0.0"
IMAGERY_STRATEGY = "seasonal_median_composite"
COMPOSITE_METHOD = "median"

# Tier 1: ±15 days around requested anchor (30-day seasonal window).
COMPOSITE_WINDOW_DAYS_BEFORE = 15
COMPOSITE_WINDOW_DAYS_AFTER = 15

# Tier 2: widened search when tier 1 is empty (configurable maximum).
COMPOSITE_WINDOW_MAX_DAYS_BEFORE = 60
COMPOSITE_WINDOW_MAX_DAYS_AFTER = 60

# Performance cap per epoch.
MAX_SCENES_PER_COMPOSITE = 12

# Minimum scenes required; fewer raises no_imagery_found.
MIN_SCENES_PER_COMPOSITE = 1

# Warn when below preferred count.
PREFERRED_MIN_SCENES = 2

COMPOSITE_PLATFORM_ID_T1 = "COMPOSITE/MEDIAN/t1"
COMPOSITE_PLATFORM_ID_T2 = "COMPOSITE/MEDIAN/t2"


def compute_composite_window(anchor_date: date) -> tuple[date, date]:
    """Deterministic tier-1 temporal window centered on the user's requested anchor date."""
    return compute_window(
        anchor_date,
        COMPOSITE_WINDOW_DAYS_BEFORE,
        COMPOSITE_WINDOW_DAYS_AFTER,
    )


def compute_window(anchor_date: date, days_before: int, days_after: int) -> tuple[date, date]:
    """Temporal window [anchor - days_before, anchor + days_after]."""
    return (
        anchor_date - timedelta(days=days_before),
        anchor_date + timedelta(days=days_after),
    )


def _scenes_in_window(
    candidates: list[SceneCandidate],
    window_start: date,
    window_end: date,
) -> list[SceneCandidate]:
    return [c for c in candidates if window_start <= c.acquisition_date <= window_end]


def _rank_and_cap(
    scenes: list[SceneCandidate],
    anchor_date: date,
) -> list[SceneCandidate]:
    ranked = sorted(scenes, key=lambda s: _sort_key_distance_to(anchor_date, s))
    return ranked[:MAX_SCENES_PER_COMPOSITE]


def _base_fallback_provenance(anchor_date: date, tier1_start: date, tier1_end: date) -> dict[str, Any]:
    return {
        "fallback_used": False,
        "tier": 1,
        "requested_date": anchor_date.isoformat(),
        "original_window_start": tier1_start.isoformat(),
        "original_window_end": tier1_end.isoformat(),
        "fallback_window_start": tier1_start.isoformat(),
        "fallback_window_end": tier1_end.isoformat(),
        "fallback_reason": None,
        "policy_decision": "tier_1_seasonal_window",
        "fallback_policy": FALLBACK_POLICY_VERSION,
    }


def select_scenes_for_composite_with_fallback(
    candidates: list[SceneCandidate],
    anchor_date: date,
    *,
    epoch_label: str,
) -> tuple[list[SceneCandidate], date, date, dict[str, Any]]:
    """
    Tiered imagery fallback without changing the user's requested anchor dates.

    Tier 1: requested anchor ± seasonal window (±15d).
    Tier 2: widen to configurable maximum (±60d).
    Tier 3: nearest valid scene when still empty.
    """
    tier1_start, tier1_end = compute_composite_window(anchor_date)
    fallback = _base_fallback_provenance(anchor_date, tier1_start, tier1_end)

    tier1_scenes = _scenes_in_window(candidates, tier1_start, tier1_end)
    if tier1_scenes:
        return _rank_and_cap(tier1_scenes, anchor_date), tier1_start, tier1_end, fallback

    tier2_start, tier2_end = compute_window(
        anchor_date,
        COMPOSITE_WINDOW_MAX_DAYS_BEFORE,
        COMPOSITE_WINDOW_MAX_DAYS_AFTER,
    )
    tier2_scenes = _scenes_in_window(candidates, tier2_start, tier2_end)
    if tier2_scenes:
        fallback.update(
            {
                "fallback_used": True,
                "tier": 2,
                "fallback_window_start": tier2_start.isoformat(),
                "fallback_window_end": tier2_end.isoformat(),
                "fallback_reason": (
                    f"No scenes in tier-1 {epoch_label} window "
                    f"[{tier1_start.isoformat()}, {tier1_end.isoformat()}]; "
                    "widened search to maximum policy window."
                ),
                "policy_decision": "tier_2_widened_window",
            }
        )
        return _rank_and_cap(tier2_scenes, anchor_date), tier2_start, tier2_end, fallback

    if candidates:
        nearest = min(candidates, key=lambda s: _sort_key_distance_to(anchor_date, s))
        scene_date = nearest.acquisition_date
        fallback.update(
            {
                "fallback_used": True,
                "tier": 3,
                "fallback_window_start": scene_date.isoformat(),
                "fallback_window_end": scene_date.isoformat(),
                "fallback_reason": (
                    f"No scenes in tier-2 maximum window "
                    f"[{tier2_start.isoformat()}, {tier2_end.isoformat()}]; "
                    f"selected nearest scene {nearest.scene_id} on {scene_date.isoformat()}."
                ),
                "policy_decision": "tier_3_nearest_scene",
                "nearest_scene_id": nearest.scene_id,
                "nearest_scene_date": scene_date.isoformat(),
            }
        )
        return [nearest], scene_date, scene_date, fallback

    raise SatQueryError(
        "no_imagery_found",
        f"No Sentinel-2 scenes available for {epoch_label} anchor "
        f"{anchor_date.isoformat()} after imagery fallback policy "
        f"(tier-1 ±{COMPOSITE_WINDOW_DAYS_BEFORE}d, tier-2 ±{COMPOSITE_WINDOW_MAX_DAYS_BEFORE}d). "
        "Try different dates or increase cloud_cover_max.",
        status_code=404,
    )


def select_scenes_for_composite(
    candidates: list[SceneCandidate],
    anchor_date: date,
    *,
    epoch_label: str,
) -> tuple[list[SceneCandidate], date, date]:
    """
    Select scenes within the tier-1 anchor window only (strict, for unit tests).

    Raises SatQueryError when no scenes fall in the window.
    """
    scenes, window_start, window_end, _ = select_scenes_for_composite_with_fallback(
        candidates,
        anchor_date,
        epoch_label=epoch_label,
    )
    tier1_start, tier1_end = compute_composite_window(anchor_date)
    if window_start != tier1_start or window_end != tier1_end:
        raise SatQueryError(
            "no_imagery_found",
            f"No Sentinel-2 scenes in {epoch_label} composite window "
            f"[{tier1_start.isoformat()}, {tier1_end.isoformat()}] for anchor "
            f"{anchor_date.isoformat()}. Try widening the date range or increasing "
            "cloud_cover_max.",
            status_code=404,
        )
    return scenes, window_start, window_end


def _epoch_provenance(
    *,
    epoch: str,
    requested_date: date,
    window_start: date,
    window_end: date,
    scenes: list[SceneCandidate],
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scene_dates = [s.acquisition_date.isoformat() for s in scenes]
    warnings: list[str] = []
    if len(scenes) < PREFERRED_MIN_SCENES:
        warnings.append(
            f"{epoch}_low_scene_count: only {len(scenes)} scene(s) in composite window; "
            f"preferred minimum is {PREFERRED_MIN_SCENES}."
        )
    prov: dict[str, Any] = {
        "epoch": epoch,
        "requested_date": requested_date.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "scene_count": len(scenes),
        "scene_dates": scene_dates,
        "scene_ids": [s.scene_id for s in scenes],
        "scene_platform_ids": [s.platform_id for s in scenes],
        "warnings": warnings,
    }
    if fallback:
        prov["fallback"] = fallback
        if fallback.get("fallback_used"):
            warnings.append(
                f"{epoch}_imagery_fallback: {fallback.get('policy_decision')} — "
                f"{fallback.get('fallback_reason')}"
            )
    return prov


def build_composite_scene(
    scenes: list[SceneCandidate],
    *,
    epoch: str,
    requested_date: date,
    window_start: date,
    window_end: date,
    fallback: dict[str, Any] | None = None,
) -> ImageryScene:
    """Build an ImageryScene representing a median composite epoch."""
    platform_id = COMPOSITE_PLATFORM_ID_T1 if epoch == "t1" else COMPOSITE_PLATFORM_ID_T2
    mean_cloud = round(sum(s.cloud_cover_percent for s in scenes) / len(scenes), 2)
    epoch_meta = _epoch_provenance(
        epoch=epoch,
        requested_date=requested_date,
        window_start=window_start,
        window_end=window_end,
        scenes=scenes,
        fallback=fallback,
    )
    return ImageryScene(
        scene_id=f"composite-{epoch}-{requested_date.isoformat()}",
        acquisition_date=requested_date,
        cloud_cover_percent=mean_cloud,
        preview_url=None,
        platform_id=platform_id,
        metadata={
            "imagery_strategy": IMAGERY_STRATEGY,
            "composite_method": COMPOSITE_METHOD,
            **epoch_meta,
        },
    )


def build_composite_epochs(
    candidates: list[SceneCandidate],
    *,
    requested_start: date,
    requested_end: date,
) -> tuple[list[ImageryScene], dict[str, Any]]:
    """
    Build T1 and T2 median-composite ImageryScene records with full provenance.

    User-requested anchor dates are preserved on ImageryScene.acquisition_date.
    """
    if not candidates:
        raise SatQueryError(
            "no_imagery_after_cloud_filter",
            "All scenes were rejected by cloud filtering.",
            status_code=404,
        )

    t1_scenes, t1_start, t1_end, t1_fallback = select_scenes_for_composite_with_fallback(
        candidates, requested_start, epoch_label="T1"
    )
    t2_scenes, t2_start, t2_end, t2_fallback = select_scenes_for_composite_with_fallback(
        candidates, requested_end, epoch_label="T2"
    )

    if t1_start > t2_end:
        raise SatQueryError(
            "invalid_date_range",
            "Composite T1 window ends after T2 window starts. Check earlier_date and later_date.",
            status_code=400,
        )

    t1_scene = build_composite_scene(
        t1_scenes,
        epoch="t1",
        requested_date=requested_start,
        window_start=t1_start,
        window_end=t1_end,
        fallback=t1_fallback,
    )
    t2_scene = build_composite_scene(
        t2_scenes,
        epoch="t2",
        requested_date=requested_end,
        window_start=t2_start,
        window_end=t2_end,
        fallback=t2_fallback,
    )

    t1_prov = t1_scene.metadata
    t2_prov = t2_scene.metadata
    warnings: list[str] = list(t1_prov.get("warnings", [])) + list(t2_prov.get("warnings", []))

    if is_cross_season_pair(requested_start, requested_end):
        warnings.append(
            "cross_season_comparison: requested T1/T2 anchor months differ by more than "
            "3 months; composites reduce but do not eliminate phenology false positives."
        )

    fallback_events: list[dict[str, Any]] = []
    for epoch_key, fb in (("t1", t1_fallback), ("t2", t2_fallback)):
        if fb.get("fallback_used"):
            fallback_events.append({"epoch": epoch_key, **fb})

    seasonality = build_seasonality_provenance(
        requested_start=requested_start,
        requested_end=requested_end,
        selected_dates=[requested_start, requested_end],
        selection_policy=COMPOSITE_POLICY_VERSION,
    )
    seasonality["imagery_strategy"] = IMAGERY_STRATEGY
    seasonality["composite_method"] = COMPOSITE_METHOD
    if warnings:
        seasonality["warnings"] = warnings
        seasonality["dates_adjusted"] = True

    composite_provenance: dict[str, Any] = {
        "imagery_strategy": IMAGERY_STRATEGY,
        "composite_method": COMPOSITE_METHOD,
        "seasonality_policy": SEASONALITY_POLICY_VERSION,
        "selection_policy": COMPOSITE_POLICY_VERSION,
        "fallback_policy": FALLBACK_POLICY_VERSION,
        "t1": {
            "requested_date": t1_prov["requested_date"],
            "window_start": t1_prov["window_start"],
            "window_end": t1_prov["window_end"],
            "scene_count": t1_prov["scene_count"],
            "scene_dates": t1_prov["scene_dates"],
            "fallback": t1_fallback,
        },
        "t2": {
            "requested_date": t2_prov["requested_date"],
            "window_start": t2_prov["window_start"],
            "window_end": t2_prov["window_end"],
            "scene_count": t2_prov["scene_count"],
            "scene_dates": t2_prov["scene_dates"],
            "fallback": t2_fallback,
        },
        "fallback_events": fallback_events,
        "warnings": warnings,
    }

    return [t1_scene, t2_scene], composite_provenance


def is_composite_scene(scene: ImageryScene) -> bool:
    meta = scene.metadata or {}
    return (
        meta.get("imagery_strategy") == IMAGERY_STRATEGY
        or (scene.platform_id or "").startswith("COMPOSITE/MEDIAN/")
    )
