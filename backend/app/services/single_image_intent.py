"""Single-image upload query intent routing (VQA vs scene caption)."""

from __future__ import annotations

from app.schemas.planning import QueryIntent

_CAPTION_PHRASES = (
    "describe this scene",
    "describe this satellite scene",
    "describe the satellite scene",
    "give a caption",
    "caption for this",
    "caption for the",
    "what does this image show",
    "what does this scene show",
    "what does this satellite image show",
    "what does this satellite scene show",
)


def single_image_intent_from_query(query: str) -> QueryIntent:
    """
    Distinguish scene-description (caption) from targeted VQA on uploaded images.

    Caption: general scene description ("Describe this satellite scene.").
    VQA: specific interrogative or analytical questions ("What land-cover types are visible?").
    """
    q = query.strip().lower()
    if not q:
        return QueryIntent.SINGLE_IMAGE_VQA

    if any(phrase in q for phrase in _CAPTION_PHRASES):
        return QueryIntent.SINGLE_IMAGE_CAPTION

    if "surface pattern" in q and q.startswith("describe"):
        return QueryIntent.SINGLE_IMAGE_CAPTION

    if q.startswith("describe ") and (" scene" in q or "satellite scene" in q):
        return QueryIntent.SINGLE_IMAGE_CAPTION

    if "?" in q:
        if any(
            q.startswith(prefix)
            for prefix in ("what ", "which ", "how ", "where ", "when ", "who ")
        ):
            return QueryIntent.SINGLE_IMAGE_VQA

    if any(
        marker in q
        for marker in (
            "what land-cover",
            "what land cover",
            "what types",
            "what structures",
            "how many",
            "which ",
        )
    ):
        return QueryIntent.SINGLE_IMAGE_VQA

    # Imperative describe focused on image content (Phase 10 VQA compat).
    if q.startswith("describe ") and "in this image" in q:
        return QueryIntent.SINGLE_IMAGE_VQA

    if q.startswith("describe "):
        return QueryIntent.SINGLE_IMAGE_CAPTION

    return QueryIntent.SINGLE_IMAGE_VQA
