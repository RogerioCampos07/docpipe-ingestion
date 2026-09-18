"""Publish persisted outbox events with bounded retries."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event
from time import sleep

from docpipe_ingestion.application.events import DocumentReceivedV1
from docpipe_ingestion.application.ports import BrokerPublisher, UnitOfWork
from docpipe_ingestion.domain.models import OutboxEvent

type UnitOfWorkFactory = Callable[[], UnitOfWork]
type Clock = Callable[[], datetime]
type Sleeper = Callable[[float], None]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PublisherSettings:
    batch_size: int
    max_attempts: int
    backoff_seconds: float
    polling_seconds: float


class OutboxPublisher:
    """Single-instance polling publisher with at-least-once delivery."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        broker: BrokerPublisher,
        settings: PublisherSettings,
        clock: Clock = lambda: datetime.now(UTC),
        sleeper: Sleeper = sleep,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._broker = broker
        self._settings = settings
        self._clock = clock
        self._sleep = sleeper

    def process_batch(self) -> int:
        """Publish at most one configured batch and return successes."""
        with self._unit_of_work_factory() as unit_of_work:
            events = unit_of_work.outbox_events.list_pending(
                limit=self._settings.batch_size,
                max_attempts=self._settings.max_attempts,
            )
        published = 0
        for event in events:
            try:
                self._validate_and_publish(event)
            except Exception as error:
                summary = type(error).__name__
                with self._unit_of_work_factory() as unit_of_work:
                    unit_of_work.outbox_events.record_failure(
                        event.id,
                        summary,
                    )
                    unit_of_work.commit()
                logger.warning(
                    'outbox publication failed event_id=%s '
                    'attempt=%d error=%s',
                    event.id,
                    event.attempts + 1,
                    summary,
                )
                self._sleep(
                    min(
                        self._settings.backoff_seconds * (2**event.attempts),
                        60.0,
                    )
                )
                continue
            with self._unit_of_work_factory() as unit_of_work:
                unit_of_work.outbox_events.mark_published(
                    event.id,
                    self._clock(),
                )
                unit_of_work.commit()
            published += 1
            logger.info('outbox event published event_id=%s', event.id)
        return published

    def _validate_and_publish(self, event: OutboxEvent) -> None:
        payload = DocumentReceivedV1.model_validate(event.payload)
        if payload.event_id != event.id:
            raise ValueError('event identifier does not match outbox')
        if payload.document_id != event.aggregate_id:
            raise ValueError('document identifier does not match outbox')
        self._broker.publish(event)

    def run(self, stop_event: Event) -> None:
        """Poll until a controlled shutdown is requested."""
        try:
            while not stop_event.is_set():
                self.process_batch()
                stop_event.wait(self._settings.polling_seconds)
        finally:
            self._broker.close()
