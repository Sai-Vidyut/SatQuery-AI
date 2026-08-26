from __future__ import annotations

from functools import lru_cache

from app.adapters.rsvlm.base import RemoteSensingVLM
from app.adapters.rsvlm.development import DevelopmentGeoChatVLM
from app.adapters.rsvlm.geochat_service import GeoChatServiceVLM
from app.core.config import get_settings
from app.core.errors import SatQueryError


@lru_cache
def get_geochat_vlm() -> RemoteSensingVLM:
    settings = get_settings()
    provider = settings.geochat_vqa_provider.lower()
    if provider == "development":
        return DevelopmentGeoChatVLM()
    if provider == "geochat_service":
        if not settings.geochat_service_url:
            raise SatQueryError(
                "geochat_service_misconfigured",
                "GEOCHAT_SERVICE_URL is required when GEOCHAT_VQA_PROVIDER=geochat_service.",
                status_code=500,
            )
        return GeoChatServiceVLM(settings.geochat_service_url, settings.geochat_model_id)
    raise SatQueryError(
        "geochat_vqa_misconfigured",
        f"Unknown GEOCHAT_VQA_PROVIDER: {settings.geochat_vqa_provider}",
        status_code=500,
    )
