from datetime import UTC, datetime
from uuid import UUID

from docpipe_ingestion.domain.models import (
    Document,
    DocumentStatus,
    OutboxEvent,
)
from docpipe_ingestion.infrastructure.database.engine import SessionFactory
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)

DOCUMENT_ID = UUID('12345678-1234-5678-1234-567812345678')
CORRELATION_ID = UUID('87654321-4321-8765-4321-876543218765')
EVENT_ID = UUID('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)
PUBLISHED_ATTEMPTS = 2


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


def _event() -> OutboxEvent:
    return OutboxEvent(
        id=EVENT_ID,
        aggregate_id=DOCUMENT_ID,
        event_type='test.event',
        payload={'document_id': str(DOCUMENT_ID)},
        created_at=NOW,
    )


def test_repositories_round_trip_document_and_outbox_event(
    session_factory: SessionFactory,
) -> None:
    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        unit_of_work.documents.add(_document())
        unit_of_work.outbox_events.add(_event())
        unit_of_work.commit()

    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        document = unit_of_work.documents.get(DOCUMENT_ID)
        event = unit_of_work.outbox_events.get(EVENT_ID)

    assert document == _document()
    assert event == _event()
    assert document is not None
    assert document.created_at.tzinfo is UTC


def test_unit_of_work_rolls_back_uncommitted_changes(
    session_factory: SessionFactory,
) -> None:
    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        unit_of_work.documents.add(_document())

    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        assert unit_of_work.documents.get(DOCUMENT_ID) is None


def test_document_repository_lists_storage_keys(
    session_factory: SessionFactory,
) -> None:
    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        unit_of_work.documents.add(_document())
        unit_of_work.commit()

    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        assert unit_of_work.documents.contains_storage_key('opaque-key')
        assert not unit_of_work.documents.contains_storage_key('missing')
        assert unit_of_work.documents.list_storage_keys() == {'opaque-key'}


def test_outbox_repository_tracks_failure_and_confirmed_publication(
    session_factory: SessionFactory,
) -> None:
    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        unit_of_work.documents.add(_document())
        unit_of_work.outbox_events.add(_event())
        unit_of_work.commit()

    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        pending = unit_of_work.outbox_events.list_pending(
            limit=10,
            max_attempts=5,
        )
        unit_of_work.outbox_events.record_failure(EVENT_ID, 'timeout')
        unit_of_work.commit()
    assert pending == [_event()]

    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        failed = unit_of_work.outbox_events.get(EVENT_ID)
        assert failed is not None
        assert failed.attempts == 1
        assert failed.last_error == 'timeout'
        unit_of_work.outbox_events.mark_published(EVENT_ID, NOW)
        unit_of_work.commit()

    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        assert (
            unit_of_work.outbox_events.list_pending(
                limit=10,
                max_attempts=5,
            )
            == []
        )
        event = unit_of_work.outbox_events.get(EVENT_ID)
        document = unit_of_work.documents.get(DOCUMENT_ID)
    assert event is not None
    assert event.published_at == NOW
    assert event.attempts == PUBLISHED_ATTEMPTS
    assert event.last_error is None
    assert document is not None
    assert document.status is DocumentStatus.PUBLISHED
