"""Publish persisted outbox events with bounded retries."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Event
from time import perf_counter, sleep
from uuid import UUID

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import SpanKind

from docpipe_ingestion.application.events import DocumentReceivedV1
from docpipe_ingestion.application.ports import BrokerPublisher, UnitOfWork
from docpipe_ingestion.domain.models import OutboxEvent
from docpipe_ingestion.infrastructure.observability.context import correlated
from docpipe_ingestion.infrastructure.observability.metrics import Metrics
from docpipe_ingestion.infrastructure.observability.tracing import span

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

    def __init__(  # noqa: PLR0913
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        broker: BrokerPublisher,
        settings: PublisherSettings,
        clock: Clock = lambda: datetime.now(UTC),
        sleeper: Sleeper = sleep,
        metrics: Metrics | None = None,
        tracer_provider: TracerProvider | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._broker = broker
        self._settings = settings
        self._clock = clock
        self._sleep = sleeper
        self._metrics = metrics
        self._tracer_provider = tracer_provider

    def process_batch(self) -> int:
        """Publish at most one configured batch and return successes."""
        published = 0
        for _ in range(self._settings.batch_size):
            with self._unit_of_work_factory() as unit_of_work:
                now = self._clock()
                events = unit_of_work.outbox_events.list_pending(
                    limit=1,
                    max_attempts=self._settings.max_attempts,
                    eligible_at=now,
                    lock=True,
                )
                if not events:
                    break
                event = events[0]
                correlation = UUID(str(event.payload['correlation_id']))
                attempt_started = perf_counter()
                if self._metrics is not None:
                    self._metrics.publication_attempts.inc()
                try:
                    with (
                        correlated(correlation),
                        span(
                            'outbox.publish_attempt',
                            provider=self._tracer_provider,
                            carrier=event.trace_context,
                            kind=SpanKind.PRODUCER,
                            attributes={
                                'docpipe.correlation_id': str(correlation)
                            },
                        ),
                    ):
                        self._validate_and_publish(event)
                        if self._metrics is not None:
                            self._metrics.publications_confirmed.inc()
                except Exception as error:
                    summary = type(error).__name__
                    delay = min(
                        self._settings.backoff_seconds * (2**event.attempts),
                        60.0,
                    )
                    unit_of_work.outbox_events.record_failure(
                        event.id,
                        summary,
                        next_attempt_at=now + timedelta(seconds=delay),
                    )
                    unit_of_work.commit()
                    with correlated(correlation):
                        logger.warning(
                            'outbox publication failed',
                            extra={
                                'operation': 'outbox.publish',
                                'status': 'retry',
                                'attempt': event.attempts + 1,
                                'dependency_type': 'broker',
                                'dependency_backend': 'rabbitmq',
                                'error_category': summary,
                            },
                        )
                    if self._metrics is not None:
                        self._metrics.publication_failures.labels(
                            summary
                        ).inc()
                        self._metrics.publication_duration.labels(
                            'failure'
                        ).observe(perf_counter() - attempt_started)
                    self._sleep(delay)
                    break
                unit_of_work.outbox_events.mark_published(
                    event.id,
                    now,
                )
                unit_of_work.commit()
            published += 1
            if self._metrics is not None:
                self._metrics.publication_duration.labels('success').observe(
                    perf_counter() - attempt_started
                )
            with correlated(correlation):
                logger.info(
                    'outbox event published',
                    extra={
                        'operation': 'outbox.publish',
                        'status': 'persisted',
                        'duration_ms': round(
                            (perf_counter() - attempt_started) * 1000, 3
                        ),
                        'dependency_type': 'broker',
                        'dependency_backend': 'rabbitmq',
                    },
                )
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
                started = perf_counter()
                outcome = 'success'
                try:
                    self.process_batch()
                except Exception:
                    outcome = 'failure'
                    raise
                finally:
                    if self._metrics is not None:
                        self._metrics.worker_cycles.labels(outcome).inc()
                        self._metrics.worker_cycle_duration.labels(
                            outcome
                        ).observe(perf_counter() - started)
                stop_event.wait(self._settings.polling_seconds)
        finally:
            self._broker.close()
