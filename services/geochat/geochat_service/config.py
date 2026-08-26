"""Service configuration — no secrets committed."""

from __future__ import annotations

import os
from dataclasses import dataclass


PROMPT_SYSTEM = (
    "A chat between a curious user and an artificial intelligence assistant. "
    "The assistant gives helpful, detailed, and polite answers to the user's questions."
)

LOAD_STRATEGY = "geochat_upstream_8bit_device_map_auto_deferred_clip504"
DEFAULT_MODEL_ID = "MBZUAI/geochat-7B"


@dataclass(frozen=True)
class ServiceConfig:
    model_id: str
    geochat_src: str | None
    host: str
    port: int
    eager_load: bool
    hf_token: str | None
    service_version: str

    @classmethod
    def from_env(cls) -> ServiceConfig:
        return cls(
            model_id=os.environ.get("GEOCHAT_MODEL_ID", DEFAULT_MODEL_ID),
            geochat_src=os.environ.get("GEOCHAT_SRC"),
            host=os.environ.get("GEOCHAT_SERVICE_HOST", "0.0.0.0"),
            port=int(os.environ.get("GEOCHAT_SERVICE_PORT", "8080")),
            eager_load=os.environ.get("GEOCHAT_EAGER_LOAD", "true").lower() == "true",
            hf_token=os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN"),
            service_version=os.environ.get("GEOCHAT_SERVICE_VERSION", "0.1.0"),
        )
