"""Bi-temporal change query detection for uploaded image pairs."""

from __future__ import annotations

_CHANGE_MARKERS = (
    "what changed",
    "where did the change",
    "where did changes",
    "what areas changed",
    "areas changed",
    "change occur",
    "changes occur",
    "between these two",
    "between the two",
    "built-up area",
    "built up area",
    "vegetation loss",
    "land cover change",
    "land-cover change",
    "increased",
    "decreased",
    "remained unchanged",
    "difference between",
    "temporal change",
    "over time",
)


def is_bi_temporal_change_query(query: str) -> bool:
    """Return True when the query requests bi-temporal change understanding."""
    q = query.strip().lower()
    if not q:
        return False
    if any(marker in q for marker in _CHANGE_MARKERS):
        return True
    if "change" in q and ("?" in q or q.startswith("has ") or q.startswith("where ")):
        return True
    return False
