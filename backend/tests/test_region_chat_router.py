"""Tests for deterministic region chat routing."""

from __future__ import annotations

import pytest

from app.services.region_chat_router import (
    RegionChatClassification,
    classify_region_chat_message,
    is_out_of_scope_message,
)
from app.services.session_store import ConversationTurn


@pytest.mark.parametrize(
    ("message", "expected_route", "expected_classification"),
    [
        ("What visible change occurred between the two dates?", "geo", RegionChatClassification.GEO),
        ("Why do you think this is vegetation loss?", "geo", RegionChatClassification.GEO),
        ("Could this be caused by seasonal variation?", "geo", RegionChatClassification.GEO),
        ("What does NDVI mean?", "geo", RegionChatClassification.GEO),
        ("Find every changed area in the city.", "geo", RegionChatClassification.GEO),
        ("What is a binary search tree?", "general", RegionChatClassification.GENERAL),
        ("Write a Java program for inheritance.", "general", RegionChatClassification.GENERAL),
        ("Who is the current president of India?", "general", RegionChatClassification.GENERAL),
        ("hello", "general", RegionChatClassification.GENERAL),
        ("hey there", "general", RegionChatClassification.GENERAL),
        ("What is Java inheritance?", "general", RegionChatClassification.GENERAL),
    ],
)
def test_classify_required_routing_cases(message, expected_route, expected_classification):
    decision = classify_region_chat_message(
        message,
        region_id="change-region-01",
        prior_turns=[],
    )
    assert decision.route == expected_route
    assert decision.classification == expected_classification


def test_out_of_scope_geo_stays_on_geo_route():
    decision = classify_region_chat_message(
        "Find other changed areas in the whole city",
        region_id="change-region-01",
    )
    assert decision.route == "geo"
    assert is_out_of_scope_message("Find other changed areas in the whole city") is True


def test_ambiguous_defaults_to_geo_without_history():
    decision = classify_region_chat_message(
        "Can you clarify that?",
        region_id="change-region-01",
    )
    assert decision.route == "geo"
    assert decision.classification == RegionChatClassification.AMBIGUOUS


def test_ambiguous_with_geo_history_prefers_geo():
    prior = [
        ConversationTurn(
            turn_id="t0",
            turn_index=0,
            user_message="What changed between the two dates?",
            assistant_answer="Vegetation loss is visible in the selected region.",
            route="geo",
            provider="development",
            scope="selected_region",
        )
    ]
    decision = classify_region_chat_message(
        "Could there be another explanation?",
        region_id="change-region-01",
        prior_turns=prior,
    )
    assert decision.route == "geo"


def test_region_reference_boosts_geo_route():
    decision = classify_region_chat_message(
        "Explain change-region-01 in more detail",
        region_id="change-region-01",
    )
    assert decision.route == "geo"
