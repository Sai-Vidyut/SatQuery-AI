from __future__ import annotations

import pytest

from app.adapters.semantic.development import DevelopmentSemanticAnalyzer
from app.adapters.semantic.earth_engine import EarthEngineDynamicWorldBuiltAnalyzer
from app.adapters.semantic.factory import get_semantic_analyzer
from app.core.errors import SatQueryError
from app.schemas.domain import DataMode


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_factory_returns_development_analyzer(monkeypatch):
    monkeypatch.setenv("SEMANTIC_ANALYZER", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()
    analyzer = get_semantic_analyzer()
    assert isinstance(analyzer, DevelopmentSemanticAnalyzer)


def test_factory_returns_earth_engine_analyzer(monkeypatch):
    monkeypatch.setenv("SEMANTIC_ANALYZER", "earth_engine")
    from app.core.config import get_settings

    get_settings.cache_clear()
    analyzer = get_semantic_analyzer(DataMode.EARTH_ENGINE)
    assert isinstance(analyzer, EarthEngineDynamicWorldBuiltAnalyzer)


def test_factory_rejects_earth_engine_with_development_imagery(monkeypatch):
    monkeypatch.setenv("SEMANTIC_ANALYZER", "earth_engine")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(SatQueryError) as exc:
        get_semantic_analyzer(DataMode.DEVELOPMENT)
    assert exc.value.code == "semantic_analyzer_misconfigured"


def test_factory_rejects_development_imagery_with_dev_semantic(monkeypatch):
    monkeypatch.setenv("SEMANTIC_ANALYZER", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(SatQueryError) as exc:
        get_semantic_analyzer(DataMode.EARTH_ENGINE)
    assert exc.value.code == "semantic_analyzer_misconfigured"


def test_factory_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("SEMANTIC_ANALYZER", "invalid")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(SatQueryError) as exc:
        get_semantic_analyzer()
    assert exc.value.code == "semantic_analyzer_misconfigured"
