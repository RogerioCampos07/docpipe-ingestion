from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and an optional .env."""

    service_name: str = 'DocPipe Ingestion'
    environment: str = 'local'

    model_config = SettingsConfigDict(
        env_file='.env',
        env_prefix='DOCPIPE_INGESTION_',
        extra='ignore',
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide validated settings."""
    return Settings()
