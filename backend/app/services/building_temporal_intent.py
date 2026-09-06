"""Building-instance temporal query detection (Phase 5A).

Distinct from built-area / construction (MODE A) routing.
"""

from __future__ import annotations

import re

# Phrase-level markers take precedence over single-token construction keywords.
_BUILDING_INSTANCE_PHRASES: tuple[str, ...] = (
    "new buildings",
    "new building",
    "buildings that appeared",
    "building that appeared",
    "buildings appeared",
    "building appeared",
    "find new buildings",
    "find new building",
    "which buildings were built",
    "which building was built",
    "buildings were built",
    "building was built",
    "show new construction",
    "buildings built between",
    "new structures",
)

_BUILDING_INSTANCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bnew\s+buildings?\b", re.IGNORECASE),
    re.compile(r"\bbuildings?\s+(that\s+)?appeared\b", re.IGNORECASE),
    re.compile(r"\bfind\s+new\s+buildings?\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+buildings?\s+were\s+built\b", re.IGNORECASE),
)


def is_building_temporal_query(query: str) -> bool:
    """Return True when the query requests individual building temporal analysis (MODE B)."""
    q = query.strip().lower()
    if not q:
        return False
    if any(phrase in q for phrase in _BUILDING_INSTANCE_PHRASES):
        return True
    return any(pattern.search(query) for pattern in _BUILDING_INSTANCE_PATTERNS)
