from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and an optional .env."""

    service_name: str = 'DocPipe Ingestion'
    environment: str = 'local'
    database_backend: Literal['sqlite', 'postgresql'] = 'sqlite'
    database_url: str = 'sqlite:///dataset/docpipe-ingestion.db'
    sqlite_timeout_seconds: float = Field(default=5.0, gt=0)
    sqlite_wal_enabled: bool = True
    postgres_connect_timeout_seconds: int = Field(default=5, gt=0)
    postgres_pool_size: int = Field(default=3, gt=0)
    postgres_max_overflow: int = Field(default=2, ge=0)
    postgres_pool_timeout_seconds: float = Field(default=5.0, gt=0)
    postgres_statement_timeout_ms: int = Field(default=10_000, gt=0)
    postgres_lock_timeout_ms: int = Field(default=3_000, gt=0)
    storage_backend: Literal['local', 'azurite'] = 'local'
    storage_root: Path = Path('dataset/documents')
    blob_connection_string: SecretStr | None = None
    blob_container: str = Field(
        default='documents',
        pattern=r'^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$',
    )
    blob_api_version: str = '2023-11-03'
    blob_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    blob_read_timeout_seconds: float = Field(default=10.0, gt=0)
    blob_operation_timeout_seconds: int = Field(default=30, gt=0)
    blob_retry_total: int = Field(default=2, ge=0)
    blob_block_size_bytes: int = Field(default=1024 * 1024, ge=64 * 1024)
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

    @model_validator(mode='after')
    def validate_backends(self) -> Self:
        is_sqlite_url = self.database_url.startswith('sqlite:')
        if self.database_backend == 'sqlite' and not is_sqlite_url:
            raise ValueError('SQLite backend requires a SQLite database URL')
        if self.database_backend == 'postgresql' and is_sqlite_url:
            raise ValueError(
                'PostgreSQL backend requires a PostgreSQL database URL'
            )
        is_postgresql_url = self.database_url.startswith((
            'postgresql:',
            'postgresql+',
        ))
        if self.database_backend == 'postgresql' and not is_postgresql_url:
            raise ValueError(
                'PostgreSQL backend requires a PostgreSQL database URL'
            )
        missing_blob_connection = self.blob_connection_string is None
        if self.storage_backend == 'azurite' and missing_blob_connection:
            raise ValueError(
                'Azurite storage requires a blob connection string'
            )
        return self

    model_config = SettingsConfigDict(
        env_file='.env',
        env_prefix='DOCPIPE_INGESTION_',
        extra='ignore',
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide validated settings."""
    return Settings()
