from __future__ import annotations

from app.adapters.semantic.base import SemanticAnalyzer
from app.adapters.semantic.development import DevelopmentSemanticAnalyzer
from app.adapters.semantic.earth_engine import EarthEngineDynamicWorldBuiltAnalyzer
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.schemas.domain import DataMode


def get_semantic_analyzer(imagery_mode: DataMode | None = None) -> SemanticAnalyzer:
    settings = get_settings()
    analyzer = settings.semantic_analyzer

    if analyzer == "earth_engine":
        if imagery_mode == DataMode.DEVELOPMENT:
            raise SatQueryError(
                "semantic_analyzer_misconfigured",
                "Earth Engine semantic analyzer cannot be used with development imagery.",
                status_code=500,
            )
        return EarthEngineDynamicWorldBuiltAnalyzer()

    if imagery_mode == DataMode.EARTH_ENGINE and analyzer != "earth_engine":
        raise SatQueryError(
            "semantic_analyzer_misconfigured",
            "Earth Engine imagery requires SEMANTIC_ANALYZER=earth_engine.",
            status_code=500,
        )

    if analyzer != "development":
        raise SatQueryError(
            "semantic_analyzer_misconfigured",
            f"Unknown SEMANTIC_ANALYZER value: {analyzer!r}. "
            "Supported values: development, earth_engine.",
            status_code=500,
        )

    return DevelopmentSemanticAnalyzer()
