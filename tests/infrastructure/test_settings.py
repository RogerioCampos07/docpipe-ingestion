from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

from docpipe_ingestion.infrastructure.settings import Settings

DEFAULT_SQLITE_TIMEOUT_SECONDS = 5.0


def test_settings_have_safe_local_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('DOCPIPE_INGESTION_SERVICE_NAME', raising=False)
    monkeypatch.delenv('DOCPIPE_INGESTION_ENVIRONMENT', raising=False)
    settings = Settings()

    assert settings.service_name == 'DocPipe Ingestion'
    assert settings.environment == 'local'
    assert settings.database_url == 'sqlite:///dataset/docpipe-ingestion.db'
    assert settings.sqlite_timeout_seconds == DEFAULT_SQLITE_TIMEOUT_SECONDS
    assert settings.sqlite_wal_enabled is True
    assert settings.storage_root == Path('dataset/documents')
    assert settings.max_file_size_bytes == 10 * 1024 * 1024
    assert settings.storage_chunk_size_bytes == 64 * 1024
    assert settings.incomplete_file_age_seconds == 60 * 60


def test_settings_read_prefixed_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('DOCPIPE_INGESTION_ENVIRONMENT', 'test')
    settings = Settings()

    assert settings.environment == 'test'


@pytest.mark.parametrize(
    ('database_backend', 'database_url'),
    [
        ('sqlite', 'postgresql+psycopg://local'),
        ('postgresql', 'sqlite:///local.db'),
        ('postgresql', 'mysql://local'),
    ],
)
def test_settings_reject_mismatched_database_backend(
    database_backend: Literal['sqlite', 'postgresql'],
    database_url: str,
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_backend=database_backend,
            database_url=database_url,
        )


def test_local_storage_does_not_require_blob_configuration() -> None:
    settings = Settings(storage_backend='local', blob_connection_string=None)

    assert settings.storage_backend == 'local'


def test_azurite_requires_blob_connection_string() -> None:
    with pytest.raises(ValidationError):
        Settings(storage_backend='azurite', blob_connection_string=None)
