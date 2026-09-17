from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from docpipe_ingestion.domain.errors import (
    DomainValidationError,
    InvalidStatusTransitionError,
)
from docpipe_ingestion.domain.models import (
    Document,
    DocumentStatus,
    OutboxEvent,
)

DOCUMENT_ID = UUID('12345678-1234-5678-1234-567812345678')
CORRELATION_ID = UUID('87654321-4321-8765-4321-876543218765')
EVENT_ID = UUID('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


def make_document(
    *,
    status: DocumentStatus = DocumentStatus.RECEIVED,
    created_at: datetime = NOW,
    updated_at: datetime = NOW,
) -> Document:
    return Document(
        id=DOCUMENT_ID,
        original_name='sample.pdf',
        media_type='application/pdf',
        size_bytes=10,
        sha256='a' * 64,
        storage_key='opaque-key',
        status=status,
        correlation_id=CORRELATION_ID,
        created_at=created_at,
        updated_at=updated_at,
    )


def test_document_normalizes_aware_timestamps_to_utc() -> None:
    non_utc = datetime.fromisoformat('2026-09-17T09:00:00-03:00')

    document = make_document(created_at=non_utc, updated_at=non_utc)

    assert document.created_at == NOW
    assert document.updated_at == NOW
    assert document.created_at.tzinfo is UTC


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('size_bytes', 0),
        ('sha256', 'not-a-digest'),
        ('original_name', ''),
        ('media_type', ''),
        ('storage_key', ''),
    ],
)
def test_document_rejects_invalid_metadata(field: str, value: object) -> None:
    values: dict[str, object] = {
        'id': DOCUMENT_ID,
        'original_name': 'sample.pdf',
        'media_type': 'application/pdf',
        'size_bytes': 10,
        'sha256': 'a' * 64,
        'storage_key': 'opaque-key',
        'status': DocumentStatus.RECEIVED,
        'correlation_id': CORRELATION_ID,
        'created_at': NOW,
        'updated_at': NOW,
    }
    values[field] = value

    with pytest.raises(DomainValidationError):
        Document(**values)  # type: ignore[arg-type]


def test_document_rejects_naive_timestamp() -> None:
    naive = datetime(2026, 9, 17, 12)

    with pytest.raises(DomainValidationError, match='timezone'):
        make_document(created_at=naive)


def test_document_rejects_non_uuid_identifier() -> None:
    values: dict[str, object] = {
        'id': 'not-a-uuid',
        'original_name': 'sample.pdf',
        'media_type': 'application/pdf',
        'size_bytes': 10,
        'sha256': 'a' * 64,
        'storage_key': 'opaque-key',
        'status': DocumentStatus.RECEIVED,
        'correlation_id': CORRELATION_ID,
        'created_at': NOW,
        'updated_at': NOW,
    }

    with pytest.raises(DomainValidationError, match='UUID'):
        Document(**values)  # type: ignore[arg-type]


def test_document_rejects_timestamps_out_of_order() -> None:
    with pytest.raises(DomainValidationError, match='updated_at'):
        make_document(updated_at=NOW - timedelta(seconds=1))


def test_document_follows_the_initial_lifecycle() -> None:
    received = make_document()

    stored = received.transition_to(
        DocumentStatus.STORED,
        occurred_at=NOW + timedelta(seconds=1),
    )
    published = stored.transition_to(
        DocumentStatus.PUBLISHED,
        occurred_at=NOW + timedelta(seconds=2),
    )

    assert received.status is DocumentStatus.RECEIVED
    assert stored.status is DocumentStatus.STORED
    assert published.status is DocumentStatus.PUBLISHED


def test_document_rejects_invalid_status_transition() -> None:
    document = make_document()

    with pytest.raises(InvalidStatusTransitionError):
        document.transition_to(
            DocumentStatus.PUBLISHED,
            occurred_at=NOW,
        )


def test_document_rejects_transition_time_before_last_update() -> None:
    document = make_document(updated_at=NOW + timedelta(seconds=1))

    with pytest.raises(DomainValidationError, match='transition time'):
        document.transition_to(DocumentStatus.STORED, occurred_at=NOW)


def test_outbox_event_validates_json_and_utc() -> None:
    event = OutboxEvent(
        id=EVENT_ID,
        aggregate_id=DOCUMENT_ID,
        event_type='test.event',
        payload={'nested': {'count': 1, 'values': [True, None]}},
        created_at=NOW,
    )

    assert event.created_at.tzinfo is UTC
    assert event.attempts == 0


def test_outbox_event_rejects_non_json_payload() -> None:
    with pytest.raises(DomainValidationError, match='non-JSON'):
        OutboxEvent(
            id=EVENT_ID,
            aggregate_id=DOCUMENT_ID,
            event_type='test.event',
            payload={'invalid': object()},  # type: ignore[dict-item]
            created_at=NOW,
        )


@pytest.mark.parametrize(
    'payload',
    [
        {'invalid': float('inf')},
        {1: 'non-string-key'},
    ],
)
def test_outbox_event_rejects_invalid_json_details(
    payload: object,
) -> None:
    with pytest.raises(DomainValidationError):
        OutboxEvent(
            id=EVENT_ID,
            aggregate_id=DOCUMENT_ID,
            event_type='test.event',
            payload=payload,  # type: ignore[arg-type]
            created_at=NOW,
        )


def test_outbox_event_rejects_invalid_state() -> None:
    with pytest.raises(DomainValidationError, match='event_type'):
        OutboxEvent(
            id=EVENT_ID,
            aggregate_id=DOCUMENT_ID,
            event_type='',
            payload={},
            created_at=NOW,
        )
    with pytest.raises(DomainValidationError, match='attempts'):
        OutboxEvent(
            id=EVENT_ID,
            aggregate_id=DOCUMENT_ID,
            event_type='test.event',
            payload={},
            created_at=NOW,
            attempts=-1,
        )
    with pytest.raises(DomainValidationError, match='published_at'):
        OutboxEvent(
            id=EVENT_ID,
            aggregate_id=DOCUMENT_ID,
            event_type='test.event',
            payload={},
            created_at=NOW,
            published_at=NOW - timedelta(seconds=1),
        )


def test_outbox_event_normalizes_published_timestamp() -> None:
    published_at = datetime.fromisoformat('2026-09-17T10:00:00-03:00')

    event = OutboxEvent(
        id=EVENT_ID,
        aggregate_id=DOCUMENT_ID,
        event_type='test.event',
        payload={'ratio': 1.5},
        created_at=NOW,
        published_at=published_at,
    )

    assert event.published_at == datetime(2026, 9, 17, 13, tzinfo=UTC)
