from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://careloop:careloop@localhost:5432/careloop"
    anthropic_api_key: str = ""
    triage_model: str = "claude-opus-4-8"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
