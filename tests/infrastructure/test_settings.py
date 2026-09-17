from pathlib import Path

import pytest

from docpipe_ingestion.infrastructure.settings import Settings


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


def test_settings_read_prefixed_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('DOCPIPE_INGESTION_ENVIRONMENT', 'test')
    settings = Settings()

    assert settings.environment == 'test'
