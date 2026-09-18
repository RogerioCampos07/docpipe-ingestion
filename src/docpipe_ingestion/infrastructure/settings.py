from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and an optional .env."""

    service_name: str = 'DocPipe Ingestion'
    environment: str = 'local'
    database_url: str = 'sqlite:///dataset/docpipe-ingestion.db'
    sqlite_timeout_seconds: float = Field(default=5.0, gt=0)
    sqlite_wal_enabled: bool = True
    storage_root: Path = Path('dataset/documents')
    max_file_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    storage_chunk_size_bytes: int = Field(default=64 * 1024, ge=8)
    incomplete_file_age_seconds: int = Field(default=60 * 60, gt=0)
    rabbitmq_url: str = 'amqp://docpipe:docpipe@localhost:5672/docpipe'
    rabbitmq_exchange: str = 'docpipe.events'
    rabbitmq_queue: str = 'docpipe.document.received.v1'
    rabbitmq_routing_key: str = 'document.received.v1'
    rabbitmq_timeout_seconds: float = Field(default=5.0, gt=0)
    outbox_max_attempts: int = Field(default=5, gt=0)
    outbox_backoff_seconds: float = Field(default=1.0, gt=0)
    outbox_batch_size: int = Field(default=50, gt=0)
    outbox_polling_seconds: float = Field(default=1.0, gt=0)

    model_config = SettingsConfigDict(
        env_file='.env',
        env_prefix='DOCPIPE_INGESTION_',
        extra='ignore',
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide validated settings."""
    return Settings()
