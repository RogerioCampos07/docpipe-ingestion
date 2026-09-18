from datetime import UTC, datetime
from threading import Event
from types import TracebackType
from typing import Self, cast
from uuid import UUID

from docpipe_ingestion.application.ports import UnitOfWork
from docpipe_ingestion.application.publish_outbox import (
    OutboxPublisher,
    PublisherSettings,
)
from docpipe_ingestion.domain.models import OutboxEvent

NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)
BATCH_SIZE = 10
EVENT_ID = UUID('11111111-2222-3333-4444-555555555555')
DOCUMENT_ID = UUID('12345678-1234-5678-1234-567812345678')


def _event(attempts: int = 0) -> OutboxEvent:
    return OutboxEvent(
        id=EVENT_ID,
        aggregate_id=DOCUMENT_ID,
        event_type='document.received.v1',
        payload={
            'event_id': str(EVENT_ID),
            'event_type': 'document.received',
            'event_version': 1,
            'occurred_at': NOW.isoformat(),
            'correlation_id': '87654321-4321-8765-4321-876543218765',
            'document_id': str(DOCUMENT_ID),
            'data': {
                'storage_key': f'{"a" * 32}.blob',
                'media_type': 'application/pdf',
                'size_bytes': 10,
                'sha256': 'b' * 64,
            },
        },
        created_at=NOW,
        attempts=attempts,
    )


class StubEvents:
    def __init__(self, event: OutboxEvent) -> None:
        self.event = event
        self.published = False
        self.failures: list[str] = []

    def list_pending(
        self,
        *,
        limit: int,
        max_attempts: int,
        eligible_at: datetime | None = None,
        lock: bool = False,
    ) -> list[OutboxEvent]:
        assert limit == 1
        assert eligible_at == NOW
        assert lock
        return (
            []
            if self.published or self.event.attempts >= max_attempts
            else [self.event]
        )

    def mark_published(self, event_id: UUID, published_at: datetime) -> None:
        assert event_id == EVENT_ID
        assert published_at == NOW
        self.published = True

    def record_failure(
        self,
        event_id: UUID,
        error: str,
        *,
        next_attempt_at: datetime | None = None,
    ) -> None:
        assert event_id == EVENT_ID
        assert next_attempt_at is not None
        self.failures.append(error)


class StubUow:
    def __init__(self, events: StubEvents) -> None:
        self.outbox_events = events
        self.commits = 0

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback

    def commit(self) -> None:
        self.commits += 1


class StubBroker:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.events: list[OutboxEvent] = []
        self.closed = False

    def publish(self, event: OutboxEvent) -> None:
        self.events.append(event)
        if self.error:
            raise self.error

    def close(self) -> None:
        self.closed = True


def _publisher(
    events: StubEvents, broker: StubBroker, sleeps: list[float]
) -> OutboxPublisher:
    uow = StubUow(events)
    return OutboxPublisher(
        unit_of_work_factory=lambda: cast(UnitOfWork, uow),
        broker=broker,
        settings=PublisherSettings(BATCH_SIZE, 3, 2, 1),
        clock=lambda: NOW,
        sleeper=sleeps.append,
    )


def test_confirmed_publication_marks_event() -> None:
    events = StubEvents(_event())
    broker = StubBroker()

    assert _publisher(events, broker, []).process_batch() == 1
    assert events.published
    assert broker.events == [_event()]


def test_failure_is_recorded_and_backed_off() -> None:
    events = StubEvents(_event())
    sleeps: list[float] = []

    result = _publisher(
        events,
        StubBroker(RuntimeError()),
        sleeps,
    ).process_batch()
    assert result == 0
    assert events.failures == ['RuntimeError']
    assert sleeps == [2]


def test_exhausted_event_is_not_published() -> None:
    broker = StubBroker()
    events = StubEvents(_event(attempts=3))

    assert _publisher(events, broker, []).process_batch() == 0
    assert broker.events == []


def test_uncommitted_confirmation_can_be_published_again() -> None:
    events = StubEvents(_event())
    broker = StubBroker()
    publisher = _publisher(events, broker, [])

    publisher._broker.publish(events.event)
    publisher._broker.publish(events.event)

    assert [event.id for event in broker.events] == [EVENT_ID, EVENT_ID]


def test_controlled_shutdown_closes_broker() -> None:
    broker = StubBroker()
    publisher = _publisher(StubEvents(_event()), broker, [])
    stop = Event()
    stop.set()

    publisher.run(stop)

    assert broker.closed
