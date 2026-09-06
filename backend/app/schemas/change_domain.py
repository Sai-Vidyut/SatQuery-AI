"""Competition change-domain contracts (Phase 5B)."""

from __future__ import annotations

from enum import Enum


class ChangeDomain(str, Enum):
    """Required multi-temporal change categories from the problem statement."""

    URBAN_EXPANSION = "urban_expansion"
    MINING = "mining"
    DEFORESTATION = "deforestation"
    INFRASTRUCTURE_DEVELOPMENT = "infrastructure_development"
    WATER_SHRINKAGE = "water_shrinkage"


class ClaimStrength(str, Enum):
    """Honest claim tiers — never imply causal certainty from a single index."""

    DETECTED = "detected"
    SUPPORTED = "supported"
    CANDIDATE = "candidate"


DOMAIN_CLAIM_TYPES: dict[ChangeDomain, str] = {
    ChangeDomain.URBAN_EXPANSION: "urban_expansion_candidate",
    ChangeDomain.MINING: "mining_change_candidate",
    ChangeDomain.DEFORESTATION: "vegetation_loss_candidate",
    ChangeDomain.INFRASTRUCTURE_DEVELOPMENT: "infrastructure_change_candidate",
    ChangeDomain.WATER_SHRINKAGE: "water_shrinkage_candidate",
}

SIGNIFICANCE_POLICY_VERSION = "1.0.0"
