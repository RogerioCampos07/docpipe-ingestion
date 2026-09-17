from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from docpipe_ingestion.application.errors import (
    DocumentNotFoundError,
    MetadataQueryError,
)
from docpipe_ingestion.application.get_document import GetDocument
from docpipe_ingestion.application.ports import UnitOfWork
from docpipe_ingestion.domain.models import Document, DocumentStatus

DOCUMENT_ID = UUID('12345678-1234-5678-1234-567812345678')
CORRELATION_ID = UUID('87654321-4321-8765-4321-876543218765')
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


def _document() -> Document:
    return Document(
        id=DOCUMENT_ID,
        original_name='sample.pdf',
        media_type='application/pdf',
        size_bytes=10,
        sha256='a' * 64,
        storage_key='opaque-key',
        status=DocumentStatus.STORED,
        correlation_id=CORRELATION_ID,
        created_at=NOW,
        updated_at=NOW,
    )


class StubDocumentRepository:
    def __init__(
        self,
        document: Document | None = None,
        error: Exception | None = None,
    ) -> None:
        self.document = document
        self.error = error

    def get(self, document_id: UUID) -> Document | None:
        assert document_id == DOCUMENT_ID
        if self.error is not None:
            raise self.error
        return self.document


class StubUnitOfWork:
    def __init__(self, documents: StubDocumentRepository) -> None:
        self.documents = documents

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback


def test_get_document_returns_persisted_metadata() -> None:
    unit_of_work = StubUnitOfWork(StubDocumentRepository(_document()))
    use_case = GetDocument(lambda: cast(UnitOfWork, unit_of_work))

    assert use_case.execute(DOCUMENT_ID) == _document()


def test_get_document_reports_missing_identifier() -> None:
    unit_of_work = StubUnitOfWork(StubDocumentRepository())
    use_case = GetDocument(lambda: cast(UnitOfWork, unit_of_work))

    with pytest.raises(DocumentNotFoundError):
        use_case.execute(DOCUMENT_ID)


def test_get_document_hides_repository_failure() -> None:
    repository = StubDocumentRepository(error=RuntimeError('database leaked'))
    unit_of_work = StubUnitOfWork(repository)
    use_case = GetDocument(lambda: cast(UnitOfWork, unit_of_work))

    with pytest.raises(MetadataQueryError) as captured:
        use_case.execute(DOCUMENT_ID)

    assert isinstance(captured.value.__cause__, RuntimeError)
