from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from docpipe_ingestion.api.app import create_app
from docpipe_ingestion.api.dependencies import ApplicationServices
from docpipe_ingestion.application.errors import (
    DocumentNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    InvalidFileMetadataError,
    MetadataPersistenceError,
    MetadataQueryError,
    UnsupportedFileTypeError,
)
from docpipe_ingestion.application.ingest_document import IngestDocumentCommand
from docpipe_ingestion.domain.models import Document, DocumentStatus
from docpipe_ingestion.infrastructure.settings import Settings
from docpipe_ingestion.infrastructure.storage.local import StorageWriteError

DOCUMENT_ID = UUID('12345678-1234-5678-1234-567812345678')
DOCUMENT_CORRELATION_ID = UUID('87654321-4321-8765-4321-876543218765')
REQUEST_CORRELATION_ID = UUID('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)
CONTENT = b'%PDF-1.7\nsynthetic document'


def _document(*, correlation_id: UUID = DOCUMENT_CORRELATION_ID) -> Document:
    return Document(
        id=DOCUMENT_ID,
        original_name='sample.pdf',
        media_type='application/pdf',
        size_bytes=len(CONTENT),
        sha256='a' * 64,
        storage_key='private-storage-key',
        status=DocumentStatus.STORED,
        correlation_id=correlation_id,
        created_at=NOW,
        updated_at=NOW,
    )


@dataclass
class StubIngestDocument:
    result: Document | None = None
    error: Exception | None = None
    command: IngestDocumentCommand | None = None
    received_content: bytes | None = None

    def execute(self, command: IngestDocumentCommand) -> Document:
        self.command = command
        self.received_content = command.source.read(-1)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


@dataclass
class StubGetDocument:
    result: Document | None = None
    error: Exception | None = None

    def execute(self, document_id: UUID) -> Document:
        assert document_id == DOCUMENT_ID
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _client(
    *,
    ingest: StubIngestDocument | None = None,
    query: StubGetDocument | None = None,
) -> TestClient:
    services = ApplicationServices(
        ingest_document=ingest or StubIngestDocument(result=_document()),
        get_document=query or StubGetDocument(result=_document()),
    )
    return TestClient(
        create_app(Settings(environment='test'), services=services),
        raise_server_exceptions=False,
    )


def test_post_accepts_file_and_propagates_correlation_id() -> None:
    ingest = StubIngestDocument(
        result=_document(correlation_id=REQUEST_CORRELATION_ID)
    )

    with _client(ingest=ingest) as client:
        response = client.post(
            '/v1/documents',
            files={'file': ('sample.pdf', CONTENT, 'application/pdf')},
            headers={'X-Correlation-ID': str(REQUEST_CORRELATION_ID)},
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.headers['X-Correlation-ID'] == str(REQUEST_CORRELATION_ID)
    assert response.json() == {
        'document_id': str(DOCUMENT_ID),
        'status': 'STORED',
        'correlation_id': str(REQUEST_CORRELATION_ID),
        'received_at': '2026-09-17T12:00:00Z',
    }
    assert ingest.command is not None
    assert ingest.command.original_name == 'sample.pdf'
    assert ingest.command.content_type == 'application/pdf'
    assert ingest.command.correlation_id == REQUEST_CORRELATION_ID
    assert ingest.received_content == CONTENT


def test_post_generates_correlation_id_when_header_is_absent() -> None:
    ingest = StubIngestDocument(result=_document())

    with _client(ingest=ingest) as client:
        response = client.post(
            '/v1/documents',
            files={'file': ('sample.pdf', CONTENT, 'application/pdf')},
        )

    generated = UUID(response.headers['X-Correlation-ID'])
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert ingest.command is not None
    assert ingest.command.correlation_id == generated


def test_invalid_correlation_id_uses_standard_error_shape() -> None:
    with _client() as client:
        response = client.post(
            '/v1/documents',
            files={'file': ('sample.pdf', CONTENT, 'application/pdf')},
            headers={'X-Correlation-ID': 'not-a-uuid'},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error']['code'] == 'invalid_correlation_id'
    assert UUID(response.json()['error']['correlation_id'])
    assert (
        response.json()['error']['correlation_id']
        == response.headers['X-Correlation-ID']
    )


def test_invalid_multipart_is_normalized_to_bad_request() -> None:
    with _client() as client:
        response = client.post('/v1/documents')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error']['code'] == 'invalid_request'


def test_post_rejects_more_than_one_file() -> None:
    ingest = StubIngestDocument(result=_document())

    with _client(ingest=ingest) as client:
        response = client.post(
            '/v1/documents',
            files=[
                ('file', ('first.pdf', CONTENT, 'application/pdf')),
                ('file', ('second.pdf', CONTENT, 'application/pdf')),
            ],
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error']['code'] == 'invalid_request'
    assert ingest.command is None


@pytest.mark.parametrize(
    ('error', 'expected_status', 'expected_code'),
    [
        (InvalidFileMetadataError('private metadata'), 400, 'invalid_file'),
        (EmptyFileError('empty'), 400, 'empty_file'),
        (FileTooLargeError(10), 413, 'file_too_large'),
        (UnsupportedFileTypeError('type'), 415, 'unsupported_file_type'),
        (StorageWriteError('storage path leaked'), 503, 'storage_unavailable'),
        (
            MetadataPersistenceError('private-key'),
            503,
            'persistence_unavailable',
        ),
    ],
)
def test_post_maps_expected_failures_without_internal_details(
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    ingest = StubIngestDocument(error=error)

    with _client(ingest=ingest) as client:
        response = client.post(
            '/v1/documents',
            files={'file': ('sample.pdf', CONTENT, 'application/pdf')},
        )

    body = response.json()
    assert response.status_code == expected_status
    assert body['error']['code'] == expected_code
    assert 'private-key' not in response.text
    assert 'storage path leaked' not in response.text


def test_unexpected_error_is_sanitized() -> None:
    ingest = StubIngestDocument(error=RuntimeError('private stack detail'))

    with _client(ingest=ingest) as client:
        response = client.post(
            '/v1/documents',
            files={'file': ('sample.pdf', CONTENT, 'application/pdf')},
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()['error']['code'] == 'internal_error'
    assert 'private stack detail' not in response.text


def test_get_returns_public_metadata_without_storage_details() -> None:
    with _client() as client:
        response = client.get(
            f'/v1/documents/{DOCUMENT_ID}',
            headers={'X-Correlation-ID': str(REQUEST_CORRELATION_ID)},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers['X-Correlation-ID'] == str(REQUEST_CORRELATION_ID)
    assert response.json() == {
        'document_id': str(DOCUMENT_ID),
        'original_name': 'sample.pdf',
        'media_type': 'application/pdf',
        'size_bytes': len(CONTENT),
        'sha256': 'a' * 64,
        'status': 'STORED',
        'correlation_id': str(DOCUMENT_CORRELATION_ID),
        'created_at': '2026-09-17T12:00:00Z',
        'updated_at': '2026-09-17T12:00:00Z',
    }
    assert 'storage_key' not in response.json()


@pytest.mark.parametrize(
    ('error', 'expected_status', 'expected_code'),
    [
        (DocumentNotFoundError('missing'), 404, 'document_not_found'),
        (
            MetadataQueryError('database details'),
            503,
            'persistence_unavailable',
        ),
    ],
)
def test_get_maps_expected_failures(
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    query = StubGetDocument(error=error)

    with _client(query=query) as client:
        response = client.get(f'/v1/documents/{DOCUMENT_ID}')

    assert response.status_code == expected_status
    assert response.json()['error']['code'] == expected_code
    assert 'database details' not in response.text


def test_get_rejects_malformed_document_id_as_bad_request() -> None:
    with _client() as client:
        response = client.get('/v1/documents/not-a-uuid')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error']['code'] == 'invalid_request'


def test_unknown_route_uses_standard_not_found_error() -> None:
    with _client() as client:
        response = client.get('/unknown')

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['error']['code'] == 'not_found'


def test_metrics_uses_normalized_route_without_identifiers() -> None:
    with _client() as client:
        client.get(f'/v1/documents/{DOCUMENT_ID}')
        response = client.get('/metrics')

    assert response.status_code == status.HTTP_200_OK
    assert 'route="/v1/documents/{document_id}"' in response.text
    assert str(DOCUMENT_ID) not in response.text
    assert str(REQUEST_CORRELATION_ID) not in response.text
