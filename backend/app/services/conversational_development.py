"""Deterministic conversational development replies for chat (not analysis re-submission)."""

from __future__ import annotations

import re

from app.schemas.domain import AnalysisResult, EvidenceRegion
from app.services.session_store import ConversationTurn

_GREETING_RE = re.compile(r"^(hi|hello|hey|good (?:morning|afternoon|evening))\b", re.I)


def _extract_user_message_from_prompt(question: str) -> str:
    marker = "Current user message:"
    if marker in question:
        return question.rsplit(marker, maxsplit=1)[-1].strip()
    return question.strip()


def development_region_chat_reply(
    *,
    message: str,
    region: EvidenceRegion,
    result: AnalysisResult,
    prior_turns: list[ConversationTurn],
) -> str:
    user_message = _extract_user_message_from_prompt(message)
    lowered = user_message.strip().lower()

    if _GREETING_RE.search(lowered):
        return (
            f"Hi — I can answer questions about detected region {region.id}, its before/after evidence, "
            "and the existing change analysis. What would you like to know?"
        )

    if "vegetation loss" in lowered or "vegetation" in lowered:
        hint = region.metadata.get("change_direction_hint") or "spectral decrease"
        return (
            f"For region {region.id}, the authoritative detector metadata points to "
            f"{str(hint).replace('_', ' ')} with separability {region.confidence:.0%}. "
            "I would interpret the before/after panels as a transition away from vegetated cover in the "
            "highlighted area, but this is evidence-grounded interpretation — not a confirmed land-cover label."
        )

    if "visible" in lowered and ("difference" in lowered or "change" in lowered):
        return (
            f"In region {region.id}, the supplied before/after composite shows the detected change footprint. "
            f"Separability is {region.confidence:.0%} from the existing detector output; describe what you see "
            "in the panels rather than inventing new detections."
        )

    if "basis" in lowered or "why" in lowered or "publish" in lowered or "finding" in lowered:
        return (
            f"These findings come from the completed analysis for region {region.id}: detector-backed evidence, "
            f"region separability {region.confidence:.0%}, and the before/after composite for this selected region only. "
            "I am not running a new detection — I am explaining the evidence already attached to this session."
        )

    if "ndvi" in lowered:
        return (
            "NDVI measures vegetation greenness from multispectral reflectance. In this session I can discuss how "
            f"the detected region {region.id} relates to the existing change evidence, but I do not invent new index values."
        )

    turn_hint = f" Turn {len(prior_turns) + 1}." if prior_turns else ""
    return (
        f"[development mock — not MBZUAI/geochat-7B] For region {region.id}, I can discuss the selected before/after "
        f"evidence and existing detector metadata (separability {region.confidence:.0%}). "
        f"You asked: \"{user_message}\".{turn_hint}"
    )


def development_session_chat_reply(
    *,
    message: str,
    result: AnalysisResult,
    region: EvidenceRegion | None,
    prior_turns: list[ConversationTurn],
) -> str:
    user_message = message.strip()
    lowered = user_message.lower()

    if _GREETING_RE.search(lowered):
        if region:
            return (
                f"Hi — I can answer questions about region {region.id} or the overall analysis result. "
                "Ask about detected regions, evidence, or what the current result shows."
            )
        return (
            "Hi — I can answer follow-up questions about this analysis result, its detected regions, "
            "and the evidence already shown in the inspector. What would you like to know?"
        )

    region_count = len(result.evidence)
    confidence_pct = round(result.confidence * 100)

    if region and ("basis" in lowered or "why" in lowered or "publish" in lowered or "finding" in lowered):
        return (
            f"For region {region.id}, the current analysis already completed detection with separability "
            f"{region.confidence:.0%}. I am explaining that existing evidence — not submitting a new query or "
            "regenerating the analysis summary."
        )

    if region and ("vegetation" in lowered or "change" in lowered or "difference" in lowered):
        hint = region.metadata.get("change_direction_hint") or region.type.replace("_", " ")
        return (
            f"Region {region.id} is one of {region_count} detected region(s) in this analysis "
            f"(overall confidence {confidence_pct}%). Its metadata indicates {str(hint).replace('_', ' ')} "
            f"with separability {region.confidence:.0%}. I can discuss this region using the existing evidence only."
        )

    if "region" in lowered and region is None and region_count > 0:
        return (
            f"This analysis contains {region_count} detected region(s) with overall confidence {confidence_pct}%. "
            "Select a region on the map if you want region-specific follow-up."
        )

    turn_hint = f" Turn {len(prior_turns) + 1}." if prior_turns else ""
    scope = f"region {region.id}" if region else "this analysis"
    return (
        f"[development mock — not analysis re-submission] I can discuss {scope} using the evidence already in this session "
        f"({region_count} region(s), confidence {confidence_pct}%). "
        f"You asked: \"{user_message}\".{turn_hint}"
    )
