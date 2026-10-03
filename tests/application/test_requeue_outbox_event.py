import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from docpipe_ingestion.application.errors import (
    OutboxEventNotFoundError,
    OutboxEventNotRequeueableError,
)
from docpipe_ingestion.application.requeue_outbox_event import (
    RequeueOutboxEvent,
)
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
EVENT_ID = UUID('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
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
        correlation_id=uuid4(),
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


def _exhaust_event(session_factory: SessionFactory) -> None:
    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        unit_of_work.documents.add(_document())
        unit_of_work.outbox_events.add(_event())
        unit_of_work.commit()
    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        for _ in range(3):
            unit_of_work.outbox_events.record_failure(EVENT_ID, 'timeout')
        unit_of_work.commit()


def test_requeue_exhausted_event_preserves_identifiers_and_payload(
    session_factory: SessionFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _exhaust_event(session_factory)
    use_case = RequeueOutboxEvent(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        max_attempts=3,
    )

    with caplog.at_level(
        logging.INFO,
        logger='docpipe_ingestion.application.requeue_outbox_event',
    ):
        use_case.execute(EVENT_ID)

    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        event = unit_of_work.outbox_events.get(EVENT_ID)
    assert event is not None
    assert event.id == EVENT_ID
    assert event.aggregate_id == DOCUMENT_ID
    assert event.payload == _event().payload
    assert event.attempts == 0
    assert event.next_attempt_at is None
    assert event.last_error == 'timeout'
    assert 'outbox event requeued' in caplog.text
    assert any(
        getattr(record, 'operation', None) == 'outbox.requeue'
        and getattr(record, 'event_id', None) == str(EVENT_ID)
        for record in caplog.records
    )


@pytest.mark.parametrize(
    'event_id',
    [UUID('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')],
)
def test_requeue_rejects_unknown_event(
    session_factory: SessionFactory,
    event_id: UUID,
) -> None:
    use_case = RequeueOutboxEvent(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        max_attempts=3,
    )

    with pytest.raises(OutboxEventNotFoundError):
        use_case.execute(event_id)


def test_requeue_rejects_event_before_retry_limit(
    session_factory: SessionFactory,
) -> None:
    _exhaust_event(session_factory)
    use_case = RequeueOutboxEvent(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        max_attempts=4,
    )

    with pytest.raises(OutboxEventNotRequeueableError):
        use_case.execute(EVENT_ID)
