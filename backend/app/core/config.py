from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SatQuery AI"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    imagery_provider: str = "development"  # development | earth_engine
    change_detector: str | None = None  # development | earth_engine; defaults to imagery_provider
    sar_change_detector: str | None = None  # development | earth_engine; defaults to change_detector
    semantic_analyzer: str = "development"  # development | earth_engine
    earth_engine_project: str | None = None
    # Optional: path to service account JSON (do not commit). EE also supports
    # `earthengine authenticate` or Application Default Credentials.
    google_application_credentials: str | None = None
    query_planner: str = "deterministic"  # deterministic | llm
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    @property
    def effective_change_detector(self) -> str:
        return self.change_detector or self.imagery_provider

    @property
    def effective_sar_change_detector(self) -> str:
        return self.sar_change_detector or self.change_detector or self.imagery_provider


@lru_cache
def get_settings() -> Settings:
    return Settings()
