"""Change-domain routing, claim policy, and significance ranking (Phase 5B)."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.change_domain import (
    DOMAIN_CLAIM_TYPES,
    SIGNIFICANCE_POLICY_VERSION,
    ChangeDomain,
    ClaimStrength,
)
from app.schemas.domain import EvidenceRegion, Metric

# Phrase-level domain detection (checked before single-token heuristics).
_DOMAIN_PHRASES: dict[ChangeDomain, tuple[str, ...]] = {
    ChangeDomain.URBAN_EXPANSION: (
        "urban expansion",
        "new built-up",
        "new built up",
        "built-up area",
        "built up area",
        "urban growth",
        "urban sprawl",
    ),
    ChangeDomain.DEFORESTATION: (
        "deforestation",
        "forest loss",
        "tree loss",
        "vegetation loss",
        "forest cover loss",
    ),
    ChangeDomain.WATER_SHRINKAGE: (
        "water shrinkage",
        "water-body shrinkage",
        "water body shrinkage",
        "shrinking water",
        "lake shrinkage",
        "water loss",
        "drying lake",
        "retreating water",
    ),
    ChangeDomain.INFRASTRUCTURE_DEVELOPMENT: (
        "infrastructure development",
        "infrastructure change",
        "new infrastructure",
        "road development",
        "transport infrastructure",
    ),
    ChangeDomain.MINING: (
        "mining activity",
        "mining change",
        "open pit",
        "open-pit",
        "quarry activity",
        "mine expansion",
    ),
}

_DOMAIN_TOKEN_HINTS: dict[ChangeDomain, frozenset[str]] = {
    ChangeDomain.URBAN_EXPANSION: frozenset({"urban", "sprawl", "metropolitan"}),
    ChangeDomain.DEFORESTATION: frozenset({"deforest", "deforestation", "forest", "woodland"}),
    ChangeDomain.WATER_SHRINKAGE: frozenset({"shrinkage", "shrinking", "drying", "receding"}),
    ChangeDomain.INFRASTRUCTURE_DEVELOPMENT: frozenset({"infrastructure", "highway", "railway", "pipeline"}),
    ChangeDomain.MINING: frozenset({"mining", "mine", "quarry", "excavation", "pit"}),
}

# Domain signal matrix — primary / supporting / insufficient alone.
DOMAIN_SIGNAL_MATRIX: dict[ChangeDomain, dict[str, tuple[str, ...]]] = {
    ChangeDomain.URBAN_EXPANSION: {
        "primary": ("ndbi", "built_up_increase", "dynamic_world_built_delta"),
        "supporting": ("spectral_change", "ndvi_decrease"),
        "insufficient_alone": ("spectral_change", "sar_backscatter_change"),
    },
    ChangeDomain.DEFORESTATION: {
        "primary": ("ndvi", "vegetation_loss"),
        "supporting": ("spectral_change",),
        "insufficient_alone": ("spectral_change", "sar_backscatter_change"),
    },
    ChangeDomain.WATER_SHRINKAGE: {
        "primary": ("ndwi", "water_contraction"),
        "supporting": ("spectral_change",),
        "insufficient_alone": ("spectral_change",),
    },
    ChangeDomain.INFRASTRUCTURE_DEVELOPMENT: {
        "primary": ("ndbi", "built_up_increase", "dynamic_world_built_delta"),
        "supporting": ("spectral_change", "sar_backscatter_change"),
        "insufficient_alone": ("spectral_change",),
    },
    ChangeDomain.MINING: {
        "primary": ("ndvi", "vegetation_loss", "ndbi"),
        "supporting": ("spectral_change", "sar_backscatter_change"),
        "insufficient_alone": ("spectral_change", "sar_backscatter_change"),
    },
}

_DIRECTION_ALIGNMENT: dict[ChangeDomain, frozenset[str]] = {
    ChangeDomain.URBAN_EXPANSION: frozenset({"built_up_increase"}),
    ChangeDomain.DEFORESTATION: frozenset({"vegetation_loss"}),
    ChangeDomain.WATER_SHRINKAGE: frozenset({"water_contraction"}),
    ChangeDomain.INFRASTRUCTURE_DEVELOPMENT: frozenset({"built_up_increase", "index_increase"}),
    ChangeDomain.MINING: frozenset({"vegetation_loss", "index_decrease", "built_up_increase"}),
}

_INDEX_ALIGNMENT: dict[ChangeDomain, frozenset[str]] = {
    ChangeDomain.URBAN_EXPANSION: frozenset({"ndbi"}),
    ChangeDomain.DEFORESTATION: frozenset({"ndvi"}),
    ChangeDomain.WATER_SHRINKAGE: frozenset({"ndwi"}),
    ChangeDomain.INFRASTRUCTURE_DEVELOPMENT: frozenset({"ndbi"}),
    ChangeDomain.MINING: frozenset({"ndvi", "ndbi"}),
}

_DOMAIN_LABELS: dict[ChangeDomain, str] = {
    ChangeDomain.URBAN_EXPANSION: "urban expansion",
    ChangeDomain.DEFORESTATION: "vegetation loss",
    ChangeDomain.WATER_SHRINKAGE: "water shrinkage",
    ChangeDomain.INFRASTRUCTURE_DEVELOPMENT: "infrastructure development",
    ChangeDomain.MINING: "mining-related surface change",
}

_LIMITATION_PHRASES: dict[ChangeDomain, str] = {
    ChangeDomain.URBAN_EXPANSION: (
        "This is a spectral/built-signal indication, not confirmed urban land-cover classification."
    ),
    ChangeDomain.DEFORESTATION: (
        "This is a spectral-change indication consistent with vegetation loss, "
        "not definitive proof of deforestation."
    ),
    ChangeDomain.WATER_SHRINKAGE: (
        "This is a water-index / spectral indication, not confirmed hydrological survey data."
    ),
    ChangeDomain.INFRASTRUCTURE_DEVELOPMENT: (
        "This is a built-signal / spectral indication, not confirmed infrastructure asset mapping."
    ),
    ChangeDomain.MINING: (
        "This is a spectral-change indication only — it cannot confirm mining activity "
        "without corroborating evidence."
    ),
}

# significance = 0.40*area_norm + 0.35*confidence + 0.25*domain_support
_SIGNIFICANCE_WEIGHTS = (0.40, 0.35, 0.25)


def resolve_change_domain(query: str) -> ChangeDomain | None:
    """Detect competition change domain from natural-language query."""
    q = query.strip().lower()
    if not q:
        return None

    for domain, phrases in _DOMAIN_PHRASES.items():
        if any(phrase in q for phrase in phrases):
            return domain

    tokens = set(re.findall(r"[a-z0-9]+", q))
    water_tokens = tokens & frozenset({"water", "lake", "river", "wetland", "reservoir"})
    if water_tokens and tokens & frozenset(
        {"shrink", "shrinkage", "shrinking", "shrank", "dry", "drying", "loss"}
    ):
        return ChangeDomain.WATER_SHRINKAGE
    if "vegetation" in tokens and tokens & frozenset({"loss", "decline", "decrease"}):
        return ChangeDomain.DEFORESTATION
    if tokens & _DOMAIN_TOKEN_HINTS[ChangeDomain.MINING]:
        return ChangeDomain.MINING
    if tokens & _DOMAIN_TOKEN_HINTS[ChangeDomain.INFRASTRUCTURE_DEVELOPMENT]:
        return ChangeDomain.INFRASTRUCTURE_DEVELOPMENT
    if tokens & _DOMAIN_TOKEN_HINTS[ChangeDomain.URBAN_EXPANSION]:
        return ChangeDomain.URBAN_EXPANSION
    if tokens & _DOMAIN_TOKEN_HINTS[ChangeDomain.DEFORESTATION]:
        return ChangeDomain.DEFORESTATION
    return None


def domain_uses_construction_pipeline(domain: ChangeDomain | None) -> bool:
    """Built-area semantic path helps urban and infrastructure domains."""
    return domain in {
        ChangeDomain.URBAN_EXPANSION,
        ChangeDomain.INFRASTRUCTURE_DEVELOPMENT,
    }


def domain_claim_type(domain: ChangeDomain) -> str:
    return DOMAIN_CLAIM_TYPES[domain]


def domain_label(domain: ChangeDomain) -> str:
    return _DOMAIN_LABELS[domain]


def domain_limitation(domain: ChangeDomain) -> str:
    return _LIMITATION_PHRASES[domain]


def evaluate_domain_support(
    domain: ChangeDomain,
    *,
    direction_hint: str | None,
    primary_index: str | None,
    has_semantic_built: bool = False,
    has_sar_support: bool = False,
) -> tuple[ClaimStrength, float]:
    """
    Return claim strength tier and domain-support score in [0, 1].

    DETECTED: spectral change only.
    SUPPORTED: primary index/direction aligns with domain signals.
    CANDIDATE: supported signal + optional semantic/SAR corroboration.
    """
    score = 0.0
    if primary_index and primary_index.lower() in _INDEX_ALIGNMENT.get(domain, frozenset()):
        score += 0.45
    if direction_hint and direction_hint in _DIRECTION_ALIGNMENT.get(domain, frozenset()):
        score += 0.45
    if has_semantic_built and domain in {
        ChangeDomain.URBAN_EXPANSION,
        ChangeDomain.INFRASTRUCTURE_DEVELOPMENT,
    }:
        score += 0.25
    if has_sar_support and domain in {ChangeDomain.MINING, ChangeDomain.INFRASTRUCTURE_DEVELOPMENT}:
        score += 0.15
    score = min(score, 1.0)

    if score >= 0.65 and (has_semantic_built or has_sar_support):
        return ClaimStrength.CANDIDATE, score
    if score >= 0.45:
        return ClaimStrength.SUPPORTED, score
    return ClaimStrength.DETECTED, score


def _region_area_m2(region: EvidenceRegion) -> float:
    for metric in region.metrics:
        if metric.name in {"area_m2", "estimated_area"}:
            return float(metric.value)
    return 0.0


def compute_significance_score(
    region: EvidenceRegion,
    *,
    total_changed_area_m2: float,
    domain_support_score: float,
) -> float:
    """
    Deterministic significance policy v1.0.0.

    significance = 0.40 * area_norm + 0.35 * confidence + 0.25 * domain_support

    area_norm = region_area / max(total_changed_area_m2, region_area, 1.0)
    confidence = region.confidence (detector separability proxy)
    domain_support = evaluate_domain_support score in [0, 1]
    """
    region_area = _region_area_m2(region)
    area_norm = region_area / max(total_changed_area_m2, region_area, 1.0)
    confidence = max(0.0, min(float(region.confidence), 1.0))
    domain_support = max(0.0, min(float(domain_support_score), 1.0))
    w_area, w_conf, w_domain = _SIGNIFICANCE_WEIGHTS
    return round(w_area * area_norm + w_conf * confidence + w_domain * domain_support, 4)


def rank_regions_by_significance(regions: list[EvidenceRegion]) -> list[EvidenceRegion]:
    return sorted(
        regions,
        key=lambda r: float(r.metadata.get("significance_score", 0.0)),
        reverse=True,
    )


def annotate_regions_for_domain(
    regions: list[EvidenceRegion],
    domain: ChangeDomain,
    *,
    direction_hint: str | None = None,
    primary_index: str | None = None,
    has_semantic_built: bool = False,
    has_sar_support: bool = False,
) -> list[EvidenceRegion]:
    """Attach domain claim metadata to spectral-change regions."""
    strength, support_score = evaluate_domain_support(
        domain,
        direction_hint=direction_hint,
        primary_index=primary_index,
        has_semantic_built=has_semantic_built,
        has_sar_support=has_sar_support,
    )
    claim = domain_claim_type(domain)
    total_area = sum(_region_area_m2(r) for r in regions) or 1.0
    annotated: list[EvidenceRegion] = []
    for region in regions:
        metadata = dict(region.metadata)
        metadata.setdefault("evidence_type", "spectral_change")
        metadata["change_domain"] = domain.value
        metadata["domain_support_score"] = support_score
        metadata["claim_strength"] = strength.value
        metadata["significance_policy"] = SIGNIFICANCE_POLICY_VERSION
        metadata["significance_score"] = compute_significance_score(
            region,
            total_changed_area_m2=total_area,
            domain_support_score=support_score,
        )
        existing_claim = metadata.get("claim_type", "none")
        if existing_claim in ("none", ""):
            if strength in {ClaimStrength.SUPPORTED, ClaimStrength.CANDIDATE}:
                metadata["claim_type"] = claim
            else:
                metadata["claim_type"] = "none"
        elif existing_claim in ("construction_candidate", "new_built_area") and domain in {
            ChangeDomain.URBAN_EXPANSION,
            ChangeDomain.INFRASTRUCTURE_DEVELOPMENT,
        }:
            metadata["claim_type"] = claim
            metadata["semantic_support"] = True
        annotated.append(region.model_copy(update={"metadata": metadata}))
    return rank_regions_by_significance(annotated)


def domain_metrics_from_regions(
    domain: ChangeDomain,
    regions: list[EvidenceRegion],
    detector_metadata: dict[str, Any] | None = None,
) -> list[Metric]:
    """Structured domain metrics using only measurable detector outputs."""
    detector_metadata = detector_metadata or {}
    candidate_count = sum(
        1 for r in regions if r.metadata.get("claim_type") == domain_claim_type(domain)
    )
    metrics: list[Metric] = [
        Metric(
            name="change_domain",
            value=domain.value,
            unit=None,
            source="change_domain_policy",
        ),
        Metric(
            name=f"{domain.value}_candidate_count",
            value=candidate_count,
            unit="regions",
            source="change_domain_policy",
        ),
    ]
    for key in ("area_ha", "area_m2", "changed_percentage", "histogram_confidence", "primary_index"):
        value = detector_metadata.get(key)
        if value is not None:
            metrics.append(
                Metric(
                    name=f"domain_{key}",
                    value=value,
                    unit=None,
                    source="change_domain_policy",
                )
            )
    if detector_metadata.get("change_direction_hint"):
        metrics.append(
            Metric(
                name="domain_direction_hint",
                value=detector_metadata["change_direction_hint"],
                unit=None,
                source="change_domain_policy",
            )
        )
    return metrics


def is_water_direction_ambiguous(
    domain: ChangeDomain,
    *,
    direction_hint: str | None,
    strength: ClaimStrength,
) -> bool:
    """
    True when a water-shrinkage query cannot confidently assert contraction vs expansion.

    Preserves underlying detector metadata for inspection; answer layer stays conservative.
    """
    if domain != ChangeDomain.WATER_SHRINKAGE:
        return False
    if direction_hint == "water_expansion":
        return True
    if direction_hint not in _DIRECTION_ALIGNMENT.get(domain, frozenset()):
        return True
    if strength == ClaimStrength.DETECTED:
        return True
    return False


def compose_domain_answer_clause(
    domain: ChangeDomain,
    *,
    strength: ClaimStrength,
    direction_hint: str | None,
    primary_index: str | None,
    region_count: int = 0,
    candidate_count: int = 0,
) -> str:
    from app.evidence.bi_temporal_interpretation import format_primary_index, humanize_direction_hint

    label = domain_label(domain)

    if is_water_direction_ambiguous(domain, direction_hint=direction_hint, strength=strength):
        if region_count > 0:
            return (
                "Water-related spectral change detected; the direction is inconclusive "
                f"({region_count} mapped region{'s' if region_count != 1 else ''})."
            )
        return "Water-related spectral change detected; the direction is inconclusive."

    if strength == ClaimStrength.DETECTED:
        if region_count > 0:
            return (
                f"Spectral change detected across {region_count} mapped region"
                f"{'s' if region_count != 1 else ''}; "
                f"no strong {label} signal alignment in the primary index or direction hint."
            )
        return (
            f"Spectral change detected; no strong {label} signal alignment was found "
            "in the primary index or direction hint."
        )

    index_label = format_primary_index(primary_index)
    hint_text = humanize_direction_hint(direction_hint) if direction_hint else "no directional signal"
    if strength == ClaimStrength.SUPPORTED:
        region_note = ""
        if candidate_count > 0:
            region_note = (
                f" {candidate_count} domain candidate region"
                f"{'s' if candidate_count != 1 else ''} mapped."
            )
        return (
            f"Change is consistent with {label} based on {index_label} "
            f"and a direction hint of {hint_text}.{region_note}"
        )
    return (
        f"Region is a potential {label} candidate based on {index_label}, "
        f"{hint_text}, and corroborating evidence where available."
    )
