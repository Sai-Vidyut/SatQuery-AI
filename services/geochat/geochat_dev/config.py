"""Resolve GeoChat developer configuration from environment and optional backend/.env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BACKEND_ENV = REPO_ROOT / "backend" / ".env"
REAL_ENV_TEMPLATE = REPO_ROOT / "backend" / ".env.geochat-real.example"


def _parse_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class GeoChatDevConfig:
    provider: str
    service_url: str | None
    model_id: str
    timeout_s: float
    env_file: Path | None
    env_file_loaded: bool

    @property
    def is_real_mode(self) -> bool:
        return self.provider == "geochat_service"

    @property
    def real_mode_configured(self) -> bool:
        return self.is_real_mode and bool(self.service_url)

    def redacted_service_url(self) -> str:
        if not self.service_url:
            return "(not set)"
        parsed = urlparse(self.service_url)
        host = parsed.hostname or "unknown-host"
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{host}{port}"


def load_config(*, env_file: Path | None = None) -> GeoChatDevConfig:
    """Load config from process env, optionally overlaying backend/.env when present."""
    chosen = env_file or DEFAULT_BACKEND_ENV
    file_values = _parse_dotenv(chosen) if env_file or chosen.exists() else {}

    def _get(name: str, default: str | None = None) -> str | None:
        return os.environ.get(name) or file_values.get(name) or default

    provider = (_get("GEOCHAT_VQA_PROVIDER", "development") or "development").lower()
    service_url = _get("GEOCHAT_SERVICE_URL")
    model_id = _get("GEOCHAT_MODEL_ID", "MBZUAI/geochat-7B") or "MBZUAI/geochat-7B"
    timeout_raw = _get("GEOCHAT_SERVICE_TIMEOUT_S", "120") or "120"
    try:
        timeout_s = float(timeout_raw)
    except ValueError:
        timeout_s = 120.0

    return GeoChatDevConfig(
        provider=provider,
        service_url=service_url.rstrip("/") if service_url else None,
        model_id=model_id,
        timeout_s=timeout_s,
        env_file=chosen if chosen.exists() else None,
        env_file_loaded=bool(file_values),
    )
