from __future__ import annotations

from datetime import date

from app.schemas.domain import AOI, GeoJSONGeometry, QueryRequest
from app.schemas.planning import QueryAnalysisPlan
from app.services.planner.deterministic import (
    BUILDING_CONSTRUCTION_PROFILE,
    build_deterministic_plan,
    resolve_analysis_profile,
)


def _stub_request(query: str) -> QueryRequest:
    return QueryRequest(
        query=query,
        aoi=AOI(
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[[[0.0, 0.0], [0.01, 0.0], [0.01, 0.01], [0.0, 0.01], [0.0, 0.0]]],
            )
        ),
        earlier_date=date(2024, 1, 1),
        later_date=date(2024, 6, 1),
    )


def resolve_analysis_plan(query: str) -> QueryAnalysisPlan:
    """Backward-compatible deterministic plan resolver (query string only)."""
    return build_deterministic_plan(_stub_request(query))


# Legacy alias: tests and answer engine import AnalysisPlan from here.
AnalysisPlan = QueryAnalysisPlan

__all__ = [
    "AnalysisPlan",
    "BUILDING_CONSTRUCTION_PROFILE",
    "resolve_analysis_plan",
    "resolve_analysis_profile",
]
