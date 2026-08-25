from app.core.config import get_settings
from app.adapters.imagery.base import ImageryProvider
from app.adapters.imagery.development import DevelopmentImageryProvider
from app.adapters.imagery.earth_engine import EarthEngineProvider


def get_imagery_provider() -> ImageryProvider:
    settings = get_settings()
    if settings.imagery_provider == "earth_engine":
        return EarthEngineProvider()
    return DevelopmentImageryProvider()
