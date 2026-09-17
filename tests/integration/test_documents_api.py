from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from docpipe_ingestion.api.app import create_app
from docpipe_ingestion.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.models import (
    DocumentModel,
    OutboxEventModel,
)
from docpipe_ingestion.infrastructure.settings import Settings

PDF_CONTENT = b'%PDF-1.7\nsynthetic integration document'
CORRELATION_ID = UUID('87654321-4321-8765-4321-876543218765')


def _migration_config(database_path: Path) -> Config:
    project_root = Path(__file__).parents[2]
    config = Config(project_root / 'alembic.ini')
    config.set_main_option('script_location', str(project_root / 'migrations'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{database_path}')
    return config


def _settings(
    tmp_path: Path,
    *,
    migrate: bool = True,
    max_size_bytes: int = 1024,
) -> Settings:
    database_path = tmp_path / 'api.db'
    if migrate:
        command.upgrade(_migration_config(database_path), 'head')
    return Settings(
        environment='test',
        database_url=f'sqlite:///{database_path}',
        storage_root=tmp_path / 'documents',
        max_file_size_bytes=max_size_bytes,
        storage_chunk_size_bytes=8,
        sqlite_wal_enabled=True,
    )


def _record_counts(settings: Settings) -> tuple[int, int]:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        with session_factory() as session:
            documents = session.scalar(
                select(func.count()).select_from(DocumentModel)
            )
            events = session.scalar(
                select(func.count()).select_from(OutboxEventModel)
            )
        assert documents is not None
        assert events is not None
        return documents, events
    finally:
        engine.dispose()


def test_post_then_get_persists_file_metadata_and_pending_event(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    application = create_app(settings)

    with TestClient(application) as client:
        post_response = client.post(
            '/v1/documents',
            files={
                'file': (
                    '../../synthetic.pdf',
                    PDF_CONTENT,
                    'application/pdf',
                )
            },
            headers={'X-Correlation-ID': str(CORRELATION_ID)},
        )
        document_id = UUID(post_response.json()['document_id'])
        get_response = client.get(f'/v1/documents/{document_id}')

    assert post_response.status_code == status.HTTP_202_ACCEPTED
    assert post_response.json()['status'] == 'STORED'
    assert post_response.json()['correlation_id'] == str(CORRELATION_ID)
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()['original_name'] == 'synthetic.pdf'
    assert get_response.json()['document_id'] == str(document_id)
    assert 'storage_key' not in get_response.json()
    stored_files = list(settings.storage_root.glob('*.blob'))
    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == PDF_CONTENT
    assert _record_counts(settings) == (1, 1)

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        with session_factory() as session:
            event = session.scalar(select(OutboxEventModel))
        assert event is not None
        assert event.published_at is None
        assert event.attempts == 0
        assert event.payload['document_id'] == str(document_id)
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ('content', 'filename', 'content_type', 'expected_status'),
    [
        (b'', 'empty.pdf', 'application/pdf', 400),
        (b'plain text', 'sample.txt', 'text/plain', 415),
        (b'%PDF-1234', 'large.pdf', 'application/pdf', 413),
    ],
)
def test_rejected_upload_leaves_no_file_metadata_or_event(
    tmp_path: Path,
    content: bytes,
    filename: str,
    content_type: str,
    expected_status: int,
) -> None:
    settings = _settings(tmp_path, max_size_bytes=8)

    with TestClient(create_app(settings)) as client:
        response = client.post(
            '/v1/documents',
            files={'file': (filename, content, content_type)},
        )

    assert response.status_code == expected_status
    assert _record_counts(settings) == (0, 0)
    assert list(settings.storage_root.glob('*.blob')) == []
    assert list(settings.storage_root.glob('*.part')) == []


def test_get_returns_not_found_for_unknown_document(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    missing_id = UUID('12345678-1234-5678-1234-567812345678')

    with TestClient(create_app(settings)) as client:
        response = client.get(f'/v1/documents/{missing_id}')

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['error']['code'] == 'document_not_found'


def test_unavailable_storage_returns_503_without_metadata(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    settings.storage_root.write_bytes(b'not a directory')
    missing_id = UUID('12345678-1234-5678-1234-567812345678')

    with TestClient(create_app(settings)) as client:
        response = client.post(
            '/v1/documents',
            files={'file': ('sample.pdf', PDF_CONTENT, 'application/pdf')},
        )
        get_response = client.get(f'/v1/documents/{missing_id}')

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()['error']['code'] == 'storage_unavailable'
    assert get_response.status_code == status.HTTP_404_NOT_FOUND
    assert _record_counts(settings) == (0, 0)


def test_persistence_failure_returns_503_and_preserves_orphan(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, migrate=False)

    with TestClient(create_app(settings)) as client:
        response = client.post(
            '/v1/documents',
            files={'file': ('sample.pdf', PDF_CONTENT, 'application/pdf')},
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()['error']['code'] == 'persistence_unavailable'
    stored_files = list(settings.storage_root.glob('*.blob'))
    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == PDF_CONTENT
