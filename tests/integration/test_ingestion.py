import hashlib
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import override
from uuid import UUID

import pytest
from sqlalchemy import func, select

from docpipe_ingestion.application.errors import (
    EmptyFileError,
    FileTooLargeError,
    IngestionError,
    MetadataPersistenceError,
    UnsupportedFileTypeError,
)
from docpipe_ingestion.application.ingest_document import (
    IngestDocument,
    IngestDocumentCommand,
    IngestionLimits,
)
from docpipe_ingestion.application.reconciliation import ReconcileStorage
from docpipe_ingestion.domain.models import DocumentStatus
from docpipe_ingestion.infrastructure.database.engine import SessionFactory
from docpipe_ingestion.infrastructure.database.models import OutboxEventModel
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from docpipe_ingestion.infrastructure.storage.local import LocalDocumentStorage

DOCUMENT_ID = UUID('12345678-1234-5678-1234-567812345678')
STORAGE_ID = UUID('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
EVENT_ID = UUID('11111111-2222-3333-4444-555555555555')
CORRELATION_ID = UUID('87654321-4321-8765-4321-876543218765')
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)
CONTENT = b'%PDF-1.7\nsynthetic document'


@dataclass(frozen=True, slots=True)
class InvalidIngestionCase:
    content: bytes
    filename: str
    content_type: str
    expected_error: type[IngestionError]


def _uuid_factory() -> Iterator[UUID]:
    yield DOCUMENT_ID
    yield STORAGE_ID
    yield EVENT_ID


def _use_case(
    storage: LocalDocumentStorage,
    session_factory: SessionFactory,
    *,
    failing_commit: bool = False,
) -> IngestDocument:
    identifiers = _uuid_factory()

    def unit_of_work_factory() -> SqlAlchemyUnitOfWork:
        unit_of_work_type = (
            FailingSqlAlchemyUnitOfWork
            if failing_commit
            else SqlAlchemyUnitOfWork
        )
        return unit_of_work_type(session_factory)

    return IngestDocument(
        storage=storage,
        unit_of_work_factory=unit_of_work_factory,
        limits=IngestionLimits(max_size_bytes=1024, chunk_size_bytes=8),
        clock=lambda: NOW,
        uuid_factory=lambda: next(identifiers),
    )


class FailingSqlAlchemyUnitOfWork(SqlAlchemyUnitOfWork):
    @override
    def commit(self) -> None:
        raise RuntimeError('synthetic database failure')


def test_ingestion_stores_file_and_persists_matching_metadata(
    session_factory: SessionFactory,
    tmp_path: Path,
) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')
    use_case = _use_case(storage, session_factory)

    document = use_case.execute(
        IngestDocumentCommand(
            source=BytesIO(CONTENT),
            original_name='../../synthetic.pdf',
            content_type='application/pdf',
            correlation_id=CORRELATION_ID,
        )
    )

    assert document.status is DocumentStatus.STORED
    assert document.original_name == 'synthetic.pdf'
    assert document.size_bytes == len(CONTENT)
    assert document.sha256 == hashlib.sha256(CONTENT).hexdigest()
    assert document.storage_key == f'{STORAGE_ID.hex}.blob'
    assert (storage.root / document.storage_key).read_bytes() == CONTENT
    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        assert unit_of_work.documents.get(DOCUMENT_ID) == document
    with session_factory() as session:
        event_count = session.scalar(
            select(func.count()).select_from(OutboxEventModel)
        )
        event = session.get(OutboxEventModel, EVENT_ID)
    assert event_count == 1
    assert event is not None
    assert event.aggregate_id == DOCUMENT_ID
    assert event.event_type == 'document.received.v1'
    assert event.payload['correlation_id'] == str(CORRELATION_ID)
    assert event.payload['data']['sha256'] == document.sha256


@pytest.mark.parametrize(
    'case',
    [
        InvalidIngestionCase(
            content=b'',
            filename='empty.pdf',
            content_type='application/pdf',
            expected_error=EmptyFileError,
        ),
        InvalidIngestionCase(
            content=b'plain text',
            filename='sample.txt',
            content_type='text/plain',
            expected_error=UnsupportedFileTypeError,
        ),
        InvalidIngestionCase(
            content=b'%PDF-' + (b'a' * 1_020),
            filename='large.pdf',
            content_type='application/pdf',
            expected_error=FileTooLargeError,
        ),
    ],
)
def test_invalid_ingestion_leaves_no_file_or_metadata(
    session_factory: SessionFactory,
    tmp_path: Path,
    case: InvalidIngestionCase,
) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')
    use_case = _use_case(storage, session_factory)

    with pytest.raises(case.expected_error):
        use_case.execute(
            IngestDocumentCommand(
                source=BytesIO(case.content),
                original_name=case.filename,
                content_type=case.content_type,
                correlation_id=CORRELATION_ID,
            )
        )

    assert storage.list_keys() == set()
    assert not list(storage.root.glob('*.part'))
    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        assert unit_of_work.documents.get(DOCUMENT_ID) is None
        assert unit_of_work.outbox_events.get(EVENT_ID) is None


def test_database_failure_leaves_discoverable_orphan_without_deleting_it(
    session_factory: SessionFactory,
    tmp_path: Path,
) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')
    use_case = _use_case(storage, session_factory, failing_commit=True)

    with pytest.raises(MetadataPersistenceError) as captured:
        use_case.execute(
            IngestDocumentCommand(
                source=BytesIO(CONTENT),
                original_name='synthetic.pdf',
                content_type='application/pdf',
                correlation_id=CORRELATION_ID,
            )
        )

    storage_key = captured.value.storage_key
    orphan_path = storage.root / storage_key
    assert orphan_path.exists()
    old_incomplete = storage.root / '.upload-abandoned.part'
    old_incomplete.write_bytes(b'partial')
    old_time = (NOW - timedelta(hours=2)).timestamp()
    os.utime(old_incomplete, (old_time, old_time))
    reconciliation = ReconcileStorage(
        storage=storage,
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        incomplete_file_age=timedelta(hours=1),
        clock=lambda: NOW,
    )

    report = reconciliation.execute()

    assert report.orphaned_keys == frozenset({storage_key})
    assert report.incomplete_keys == frozenset({old_incomplete.name})
    assert orphan_path.exists()
    assert old_incomplete.exists()
