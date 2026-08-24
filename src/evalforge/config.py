from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EvalForge"
    environment: str = "development"
    database_url: str = "sqlite:///./evalforge.db"
    api_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:8501,http://localhost:3000"
    log_level: str = "INFO"
    request_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(env_file=".env", env_prefix="EVALFORGE_", extra="ignore")

    @property
    def cors_origin_list(self):
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def ensure_sqlite_parent(self) -> None:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            path = self.database_url[len(prefix) :]
            if path and path != ":memory:":
                Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
