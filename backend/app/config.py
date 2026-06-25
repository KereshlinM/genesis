from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./genesis.db"
    cors_origins: str = "http://localhost:5173"

    drift_api_url: str = "http://localhost:8000"
    drift_api_key: str = ""
    horizon_api_url: str = "http://localhost:8001"
    horizon_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
