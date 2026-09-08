"""Deterministic routing for region-scoped conversational follow-ups."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from app.services.session_store import ConversationTurn

RouteKind = Literal["geo", "general"]


class RegionChatClassification(str, Enum):
    GEO = "geo"
    GENERAL = "general"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class RegionChatRouteDecision:
    route: RouteKind
    classification: RegionChatClassification
    reason: str


OUT_OF_SCOPE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bfind (?:other|all|every|any)\b", re.I),
    re.compile(r"\bwhole city\b", re.I),
    re.compile(r"\banalyze the whole\b", re.I),
    re.compile(r"\ball damaged\b", re.I),
    re.compile(r"\bsomewhere else\b", re.I),
    re.compile(r"\banother area\b", re.I),
    re.compile(r"\bdifferent region\b", re.I),
    re.compile(r"\bnew analysis\b", re.I),
    re.compile(r"\bentire (?:scene|image|aoi|area|city)\b", re.I),
    re.compile(r"\bwhat happened (?:elsewhere|outside)\b", re.I),
)


def is_out_of_scope_message(message: str) -> bool:
    return any(pattern.search(message) for pattern in OUT_OF_SCOPE_PATTERNS)


GENERAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?:hi|hello|hey)\b", re.I),
    re.compile(r"\bgood (?:morning|afternoon|evening)\b", re.I),
    re.compile(r"\bwrite (?:a |an |me )?(?:python|java|c\+\+|javascript|typescript|email|program)\b", re.I),
    re.compile(r"\bbinary search tree\b", re.I),
    re.compile(r"\brecursion in (?:java|python|c\+\+|javascript)\b", re.I),
    re.compile(r"\b(?:explain|what is)(?:\s+\w+){0,4}\s+(?:inheritance|polymorphism|linked list|sorting algorithm)\b", re.I),
    re.compile(r"\b(?:first |current )?(?:president|prime minister) of\b", re.I),
    re.compile(r"\btell me a joke\b", re.I),
    re.compile(r"\bgood laptop\b", re.I),
    re.compile(r"\bhttp\s*404\b|\b404 mean\b|\bwhat is http\b", re.I),
    re.compile(r"\bhelp me write an email\b", re.I),
    re.compile(r"\bwho (?:is|was) the (?:first|current)\b", re.I),
)

GEO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:this|selected|detected|the) region\b", re.I),
    re.compile(r"\bbefore.?after\b", re.I),
    re.compile(r"\bbetween (?:the )?(?:two dates|these dates)\b", re.I),
    re.compile(r"\b(?:visible )?change(?:d|s)?\b", re.I),
    re.compile(r"\bvegetation loss\b", re.I),
    re.compile(r"\burban expansion\b", re.I),
    re.compile(r"\bflood(?:ing|ed)?\b", re.I),
    re.compile(r"\bconstruction\b", re.I),
    re.compile(r"\bndvi\b", re.I),
    re.compile(r"\bevi\b", re.I),
    re.compile(r"\bbackscatter\b", re.I),
    re.compile(r"\bsar\b", re.I),
    re.compile(r"\bsatellite (?:imagery|scene|image)\b", re.I),
    re.compile(r"\bevidence\b", re.I),
    re.compile(r"\bdetector\b", re.I),
    re.compile(r"\bconfidence\b", re.I),
    re.compile(r"\bseparability\b", re.I),
    re.compile(r"\bland.?cover\b", re.I),
    re.compile(r"\bseasonal variation\b", re.I),
    re.compile(r"\branked highly\b", re.I),
    re.compile(r"\bdetected change\b", re.I),
    re.compile(r"\bexplain (?:the )?detected change\b", re.I),
    re.compile(r"\bwhat (?:visible )?change\b", re.I),
    re.compile(r"\bwhat happened between\b", re.I),
    re.compile(r"\bwhat does the ndvi\b", re.I),
    re.compile(r"\bwhat does ndvi mean\b", re.I),
    re.compile(r"\bcould this be\b", re.I),
    re.compile(r"\banother explanation\b", re.I),
)


def _score_patterns(message: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    return sum(1 for pattern in patterns if pattern.search(message))


def _history_text(prior_turns: list[ConversationTurn]) -> str:
    if not prior_turns:
        return ""
    parts: list[str] = []
    for turn in prior_turns:
        parts.append(turn.user_message)
        parts.append(turn.assistant_answer)
    return "\n".join(parts)


def _history_has_geo_context(prior_turns: list[ConversationTurn], region_id: str) -> bool:
    history = _history_text(prior_turns)
    if not history:
        return False
    if region_id.lower() in history.lower():
        return True
    return _score_patterns(history, GEO_PATTERNS) > 0


def classify_region_chat_message(
    message: str,
    *,
    region_id: str,
    prior_turns: list[ConversationTurn] | None = None,
) -> RegionChatRouteDecision:
    """Classify a region chat message into geo vs general routing."""
    cleaned = message.strip()
    prior = prior_turns or []
    lower = cleaned.lower()

    general_score = _score_patterns(cleaned, GENERAL_PATTERNS)
    geo_score = _score_patterns(cleaned, GEO_PATTERNS)

    if region_id.lower() in lower:
        geo_score += 2

    if is_out_of_scope_message(cleaned):
        return RegionChatRouteDecision(
            route="geo",
            classification=RegionChatClassification.GEO,
            reason="Out-of-scope geospatial request remains on the GeoChat path for scope guard handling.",
        )

    if general_score > 0 and geo_score == 0:
        return RegionChatRouteDecision(
            route="general",
            classification=RegionChatClassification.GENERAL,
            reason="Clear general-assistant intent with no geospatial or region evidence cues.",
        )

    if geo_score > 0:
        classification = (
            RegionChatClassification.GEO
            if general_score == 0
            else RegionChatClassification.AMBIGUOUS
        )
        return RegionChatRouteDecision(
            route="geo",
            classification=classification,
            reason="Geospatial, region, or evidence-related question.",
        )

    if _history_has_geo_context(prior, region_id):
        return RegionChatRouteDecision(
            route="geo",
            classification=RegionChatClassification.AMBIGUOUS,
            reason="Ambiguous message; prior conversation refers to the selected region.",
        )

    if general_score > 0:
        return RegionChatRouteDecision(
            route="general",
            classification=RegionChatClassification.GENERAL,
            reason="General knowledge or programming question without geospatial cues.",
        )

    return RegionChatRouteDecision(
        route="geo",
        classification=RegionChatClassification.AMBIGUOUS,
        reason="Ambiguous message in a region chat; defaulting to evidence-grounded GeoChat.",
    )
