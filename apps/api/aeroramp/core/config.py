from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AERORAMP_", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./aeroramp.db"
    jwt_secret: str = "development-only-change-me-use-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cors_origins: str = "http://localhost:3000"
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    upload_dir: Path = Path("storage/uploads")
    evidence_dir: Path = Path("storage/evidence")
    observation_dir: Path = Path("storage/observations")
    max_upload_mb: int = 1024
    processing_backend: str = "inline"
    default_detector: str = "motion"
    inference_fps: float = 4.0
    request_rate_limit_per_minute: int = 180

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [x.strip() for x in self.trusted_hosts.split(",") if x.strip()]

    def ensure_directories(self) -> None:
        for path in (self.upload_dir, self.evidence_dir, self.observation_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
