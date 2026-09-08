"""Deterministic inspection-priority ranking for bi-temporal EvidenceRegions (read-only)."""

from __future__ import annotations

from typing import Literal

from app.core.errors import SatQueryError
from app.evidence.bi_temporal_interpretation import CONFIDENCE_KIND
from app.schemas.bi_temporal_change import BiTemporalDetectorSummary
from app.schemas.domain import EvidenceRegion, Metric
from app.schemas.region_ranking import BiTemporalRegionRankingResult, RankedRegionItem
from app.services.session_store import SessionStore, session_store

RANKING_POLICY = "bi_temporal_inspection_priority_v1.0.0"

# Normalized weighted formula — see rank_bi_temporal_regions() docstring.
_WEIGHT_CONFIDENCE = 0.45
_WEIGHT_AREA_SHARE = 0.25
_WEIGHT_DIRECTION = 0.20
_WEIGHT_CLAIM = 0.10

_SPECIFIC_DIRECTION_HINTS = frozenset(
    {
        "vegetation_loss",
        "vegetation_gain",
        "water_expansion",
        "water_contraction",
        "built_up_increase",
        "built_up_decrease",
        "sar_backscatter_increase",
        "sar_backscatter_decrease",
    }
)
_GENERIC_DIRECTION_HINTS = frozenset({"index_increase", "index_decrease"})
_SUPPORTED_CLAIM_TYPES = frozenset(
    {
        "construction_candidate",
        "new_built_area",
        "vegetation_loss_candidate",
        "water_shrinkage_candidate",
        "mining_activity_candidate",
        "infrastructure_development_candidate",
    }
)

PriorityLabel = Literal["high", "medium", "low"]


def _metric_value(region: EvidenceRegion, name: str) -> float | None:
    for metric in region.metrics:
        if metric.name == name:
            try:
                return float(metric.value)
            except (TypeError, ValueError):
                return None
    return None


def _region_area_m2(region: EvidenceRegion) -> float:
    value = _metric_value(region, "area_m2")
    if value is not None:
        return max(value, 0.0)
    value = _metric_value(region, "estimated_area")
    if value is not None:
        return max(value, 0.0)
    return 0.0


def _resolve_direction_hint(
    region: EvidenceRegion,
    detector_summary: BiTemporalDetectorSummary | None,
) -> str | None:
    hint = region.metadata.get("change_direction_hint")
    if hint:
        return str(hint)
    if detector_summary and detector_summary.change_direction_hint:
        return detector_summary.change_direction_hint
    return None


def _resolve_confidence_kind(
    region: EvidenceRegion,
    detector_summary: BiTemporalDetectorSummary | None,
) -> str | None:
    kind = region.metadata.get("confidence_kind")
    if kind:
        return str(kind)
    if detector_summary and detector_summary.confidence_kind:
        return detector_summary.confidence_kind
    return CONFIDENCE_KIND


def _direction_signal(hint: str | None) -> float:
    if not hint or hint == "no_change":
        return 0.0
    if hint in _SPECIFIC_DIRECTION_HINTS:
        return 1.0
    if hint in _GENERIC_DIRECTION_HINTS:
        return 0.55
    return 0.75


def _claim_signal(claim_type: str | None) -> float:
    if not claim_type or claim_type == "none":
        return 0.0
    if claim_type in _SUPPORTED_CLAIM_TYPES:
        return 1.0
    strength = claim_type.lower()
    if "candidate" in strength or "supported" in strength:
        return 0.75
    return 0.5


def compute_priority_score(
    region: EvidenceRegion,
    *,
    total_region_area_m2: float,
    direction_hint: str | None,
) -> float:
    """
    Deterministic inspection priority in [0, 1].

    Formula (v1.0.0):

        priority_score =
            0.45 * confidence
          + 0.25 * area_share
          + 0.20 * direction_signal
          + 0.10 * claim_signal

    - confidence: region.confidence (histogram separability, already 0..1)
    - area_share: region_area_m2 / max(total_region_area_m2, 1.0)
      Relative share among detected regions in the session — not raw scene area.
    - direction_signal: 0 for no_change/missing; 0.55 generic index hints;
      1.0 for specific directional hints (vegetation_loss, built_up_increase, …)
    - claim_signal: 0 for none; higher when authoritative claim_type is present

    Raw metric magnitudes are normalized before weighting so one signal cannot
    dominate accidentally.
    """
    confidence = max(0.0, min(float(region.confidence), 1.0))
    region_area = _region_area_m2(region)
    area_share = region_area / max(total_region_area_m2, 1.0)
    area_share = max(0.0, min(area_share, 1.0))
    direction = _direction_signal(direction_hint)
    claim = _claim_signal(region.metadata.get("claim_type"))
    score = (
        _WEIGHT_CONFIDENCE * confidence
        + _WEIGHT_AREA_SHARE * area_share
        + _WEIGHT_DIRECTION * direction
        + _WEIGHT_CLAIM * claim
    )
    return round(max(0.0, min(score, 1.0)), 4)


def priority_label_for_score(score: float) -> PriorityLabel:
    if score >= 0.70:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def rank_bi_temporal_regions(
    *,
    session_id: str,
    detector: str,
    regions: list[EvidenceRegion],
    detector_summary: BiTemporalDetectorSummary | None = None,
) -> BiTemporalRegionRankingResult:
    """Rank authoritative regions without mutating them."""
    total_area = sum(_region_area_m2(region) for region in regions)
    scored: list[tuple[float, float, str, EvidenceRegion, str | None]] = []
    for region in regions:
        direction_hint = _resolve_direction_hint(region, detector_summary)
        score = compute_priority_score(
            region,
            total_region_area_m2=total_area,
            direction_hint=direction_hint,
        )
        scored.append((score, _region_area_m2(region), region.id, region, direction_hint))

    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))

    ranked_items: list[RankedRegionItem] = []
    for index, (score, _area, _region_id, region, direction_hint) in enumerate(scored, start=1):
        ranked_items.append(
            RankedRegionItem(
                rank=index,
                region_id=region.id,
                priority_score=score,
                priority_label=priority_label_for_score(score),
                confidence=region.confidence,
                confidence_kind=_resolve_confidence_kind(region, detector_summary),  # type: ignore[arg-type]
                change_direction_hint=direction_hint,
                claim_type=region.metadata.get("claim_type"),
                metrics=list(region.metrics),
            )
        )

    return BiTemporalRegionRankingResult(
        session_id=session_id,
        detector=detector,
        ranking_policy=RANKING_POLICY,
        regions=ranked_items,
    )


class RegionRankingService:
    def __init__(self, store: SessionStore | None = None) -> None:
        self._store = store or session_store

    def rank_session_regions(self, session_id: str) -> BiTemporalRegionRankingResult:
        session = self._store.get(session_id)
        if not session or not session.result:
            raise SatQueryError(
                "session_not_found",
                f"No result for session: {session_id}",
                status_code=404,
            )

        result = session.result
        if not result.bi_temporal_change:
            raise SatQueryError(
                "not_bi_temporal_session",
                "Region ranking requires a bi-temporal analysis session.",
                status_code=422,
            )

        return rank_bi_temporal_regions(
            session_id=session_id,
            detector=result.bi_temporal_change.detector,
            regions=list(result.evidence),
            detector_summary=result.bi_temporal_change.detector_summary,
        )


region_ranking_service = RegionRankingService()
