"""Ordered PostgreSQL/RabbitMQ races around an exhausted outbox event."""

import json
import os
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event
from time import monotonic
from types import TracebackType
from typing import Any, Self
from uuid import UUID, uuid4

import pika  # type: ignore[import-untyped]
import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from docpipe_ingestion.application.errors import OutboxEventNotRequeueableError
from docpipe_ingestion.application.events import DocumentReceivedV1
from docpipe_ingestion.application.ports import (
    BrokerPublisher,
    DocumentRepository,
    OutboxEventRepository,
)
from docpipe_ingestion.application.publish_outbox import (
    OutboxPublisher,
    PublisherSettings,
)
from docpipe_ingestion.application.requeue_outbox_event import (
    RequeueOutboxEvent,
)
from docpipe_ingestion.domain.models import (
    Document,
    DocumentStatus,
    OutboxEvent,
)
from docpipe_ingestion.infrastructure.database.engine import (
    SessionFactory,
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from docpipe_ingestion.infrastructure.messaging.rabbitmq import (
    RabbitMQPublisher,
)
from docpipe_ingestion.infrastructure.settings import Settings
from tests.integration.conftest import migrate

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.rabbitmq,
    pytest.mark.skipif(
        os.environ.get('DOCPIPE_POSTGRESQL_INTEGRATION') != '1'
        or os.environ.get('DOCPIPE_RABBITMQ_INTEGRATION') != '1',
        reason='enable isolated PostgreSQL and RabbitMQ integrations',
    ),
]

NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)
MAX_ATTEMPTS = 3
WAIT_SECONDS = 15.0
LOCK_OBSERVATION_SECONDS = 4.0


@dataclass
class RaceResources:
    engine: Engine
    factory: SessionFactory
    database_url: str
    rabbitmq_url: str
    queue: str
    routing_key: str
    channel: Any
    connection: Any


@pytest.fixture
def race_resources(
    postgresql_url: str,
    rabbitmq_url: str,
) -> Iterator[RaceResources]:
    database_name = f'docpipe_b3_{uuid4().hex}'
    database_url = (
        make_url(postgresql_url)
        .set(database=database_name)
        .render_as_string(hide_password=False)
    )
    admin_engine = create_engine(postgresql_url, isolation_level='AUTOCOMMIT')
    try:  # noqa: PLR1702 - release database, broker and engine independently
        with admin_engine.connect() as admin:
            admin.execute(text(f'CREATE DATABASE {database_name}'))
        try:
            migrate(database_url)
            settings = Settings(
                database_backend='postgresql', database_url=database_url
            )
            engine = create_database_engine(settings)
            try:
                connection = pika.BlockingConnection(
                    pika.URLParameters(rabbitmq_url)
                )
                try:
                    channel = connection.channel()
                    queue = f'docpipe-b3-{uuid4().hex}'
                    routing_key = queue
                    queue_declared = False
                    try:
                        channel.exchange_declare(
                            exchange='docpipe.events',
                            exchange_type='direct',
                            durable=True,
                        )
                        channel.queue_declare(queue=queue, durable=True)
                        queue_declared = True
                        channel.queue_bind(
                            queue=queue,
                            exchange='docpipe.events',
                            routing_key=routing_key,
                        )
                        resources = RaceResources(
                            engine=engine,
                            factory=create_session_factory(engine),
                            database_url=database_url,
                            rabbitmq_url=rabbitmq_url,
                            queue=queue,
                            routing_key=routing_key,
                            channel=channel,
                            connection=connection,
                        )
                        yield resources
                    finally:
                        if queue_declared and channel.is_open:
                            channel.queue_delete(queue=queue)
                finally:
                    connection.close()
            finally:
                engine.dispose()
        finally:
            with admin_engine.connect() as admin:
                admin.execute(
                    text(f'DROP DATABASE {database_name} WITH (FORCE)')
                )
    finally:
        admin_engine.dispose()


def _seed_exhausted(resources: RaceResources) -> tuple[Document, OutboxEvent]:
    document_id = uuid4()
    event_id = uuid4()
    document = Document(
        id=document_id,
        original_name='synthetic.pdf',
        media_type='application/pdf',
        size_bytes=10,
        sha256='a' * 64,
        storage_key=f'{uuid4().hex}.blob',
        status=DocumentStatus.STORED,
        correlation_id=uuid4(),
        created_at=NOW,
        updated_at=NOW,
    )
    payload = DocumentReceivedV1.from_document(
        document, event_id=event_id
    ).model_dump(mode='json')
    event = OutboxEvent(
        id=event_id,
        aggregate_id=document_id,
        event_type='document.received.v1',
        payload=payload,
        created_at=NOW,
    )
    with SqlAlchemyUnitOfWork(resources.factory) as unit:
        unit.documents.add(document)
        unit.outbox_events.add(event)
        unit.commit()
    with SqlAlchemyUnitOfWork(resources.factory) as unit:
        for _ in range(MAX_ATTEMPTS):
            unit.outbox_events.record_failure(event_id, 'synthetic timeout')
        unit.commit()
    return document, event


def _requeue(factory: SessionFactory) -> RequeueOutboxEvent:
    return RequeueOutboxEvent(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(factory),
        max_attempts=MAX_ATTEMPTS,
    )


def _broker(resources: RaceResources) -> RabbitMQPublisher:
    return RabbitMQPublisher(
        url=resources.rabbitmq_url,
        exchange='docpipe.events',
        queue=resources.queue,
        routing_key=resources.routing_key,
        timeout_seconds=5,
    )


def _publisher(
    factory: SessionFactory, broker: BrokerPublisher
) -> OutboxPublisher:
    return OutboxPublisher(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(factory),
        broker=broker,
        settings=PublisherSettings(
            batch_size=1,
            max_attempts=MAX_ATTEMPTS,
            backoff_seconds=0.01,
            polling_seconds=1,
        ),
        clock=lambda: NOW,
    )


def _read(
    resources: RaceResources, event_id: UUID, document_id: UUID
) -> tuple[Document, OutboxEvent]:
    with SqlAlchemyUnitOfWork(resources.factory) as unit:
        document = unit.documents.get(document_id)
        event = unit.outbox_events.get(event_id)
    assert document is not None
    assert event is not None
    return document, event


def _assert_published(resources: RaceResources, original: OutboxEvent) -> None:
    document, event = _read(resources, original.id, original.aggregate_id)
    assert document.status is DocumentStatus.PUBLISHED
    assert event.id == original.id
    assert event.aggregate_id == original.aggregate_id
    assert event.payload == original.payload
    assert event.published_at == NOW
    assert event.attempts == 1
    assert event.last_error is None
    assert event.next_attempt_at is None


def _assert_message(resources: RaceResources, original: OutboxEvent) -> None:
    method, properties, body = resources.channel.basic_get(
        queue=resources.queue, auto_ack=False
    )
    assert method is not None
    assert properties.message_id == str(original.id)
    assert properties.correlation_id == original.payload['correlation_id']
    assert json.loads(body) == original.payload
    resources.channel.basic_ack(method.delivery_tag)
    assert resources.channel.basic_get(queue=resources.queue)[0] is None


class PauseCommitUnitOfWork(SqlAlchemyUnitOfWork):
    def __init__(
        self,
        factory: SessionFactory,
        updated: Event,
        release: Event,
    ) -> None:
        super().__init__(factory)
        self.updated = updated
        self.release = release

    def __enter__(self) -> Self:
        super().__enter__()
        return self

    def commit(self) -> None:
        self.updated.set()
        assert self.release.wait(WAIT_SECONDS), (
            'requeue commit was not released'
        )
        super().commit()


def test_uncommitted_requeue_is_not_published(
    race_resources: RaceResources,
    record_property: Callable[[str, object], None],
) -> None:
    document, original = _seed_exhausted(race_resources)
    updated = Event()
    release = Event()
    use_case = RequeueOutboxEvent(
        unit_of_work_factory=lambda: PauseCommitUnitOfWork(
            race_resources.factory, updated, release
        ),
        max_attempts=MAX_ATTEMPTS,
    )
    broker = _broker(race_resources)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(use_case.execute, original.id)
            try:
                assert updated.wait(WAIT_SECONDS), 'requeue UPDATE not reached'
                assert (
                    _publisher(race_resources.factory, broker).process_batch()
                    == 0
                )
                before_document, before_event = _read(
                    race_resources, original.id, document.id
                )
                assert before_document.status is DocumentStatus.STORED
                assert before_event.attempts == MAX_ATTEMPTS
                assert before_event.published_at is None
                assert (
                    race_resources.channel.basic_get(
                        queue=race_resources.queue
                    )[0]
                    is None
                )
            finally:
                release.set()
                record_property(
                    'participant_errors', repr(_participant_errors([future]))
                )
            future.result(timeout=WAIT_SECONDS)
        assert _publisher(race_resources.factory, broker).process_batch() == 1
        _assert_published(race_resources, original)
        _assert_message(race_resources, original)
        record_property(
            'order',
            'requeue_update;worker_empty;requeue_commit;broker_confirm;db_commit',
        )
    finally:
        broker.close()


class PauseGetRepository:
    def __init__(
        self,
        delegate: OutboxEventRepository,
        read: Event,
        release: Event,
        updating: Event,
    ) -> None:
        self.delegate = delegate
        self.read = read
        self.release = release
        self.updating = updating

    def get(self, event_id: UUID) -> OutboxEvent | None:
        event = self.delegate.get(event_id)
        self.read.set()
        assert self.release.wait(WAIT_SECONDS), 'stale read was not released'
        return event

    def requeue_exhausted(self, event_id: UUID, *, max_attempts: int) -> bool:
        self.updating.set()
        return self.delegate.requeue_exhausted(
            event_id, max_attempts=max_attempts
        )

    def add(self, event: OutboxEvent) -> None:
        self.delegate.add(event)

    def list_pending(
        self,
        *,
        limit: int,
        max_attempts: int,
        eligible_at: datetime | None = None,
        lock: bool = False,
    ) -> list[OutboxEvent]:
        return self.delegate.list_pending(
            limit=limit,
            max_attempts=max_attempts,
            eligible_at=eligible_at,
            lock=lock,
        )

    def record_failure(
        self,
        event_id: UUID,
        error: str,
        *,
        next_attempt_at: datetime | None = None,
    ) -> None:
        self.delegate.record_failure(
            event_id, error, next_attempt_at=next_attempt_at
        )

    def mark_published(self, event_id: UUID, published_at: datetime) -> None:
        self.delegate.mark_published(event_id, published_at)


class PauseGetUnitOfWork:
    def __init__(
        self,
        factory: SessionFactory,
        read: Event,
        release: Event,
        updating: Event,
    ) -> None:
        self.delegate = SqlAlchemyUnitOfWork(factory)
        self.read = read
        self.release = release
        self.updating = updating

    def __enter__(self) -> Self:
        self.delegate.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.delegate.__exit__(exc_type, exc_value, traceback)

    @property
    def documents(self) -> DocumentRepository:
        return self.delegate.documents

    @property
    def outbox_events(self) -> OutboxEventRepository:
        return PauseGetRepository(
            self.delegate.outbox_events,
            self.read,
            self.release,
            self.updating,
        )

    def commit(self) -> None:
        self.delegate.commit()

    def rollback(self) -> None:
        self.delegate.rollback()


class PauseAfterConfirmBroker:
    def __init__(
        self, resources: RaceResources, confirmed: Event, release: Event
    ) -> None:
        self.delegate = _broker(resources)
        self.confirmed = confirmed
        self.release = release

    def publish(self, event: OutboxEvent) -> None:
        self.delegate.publish(event)
        self.confirmed.set()
        assert self.release.wait(WAIT_SECONDS), (
            'worker commit was not released'
        )

    def is_ready(self) -> bool:
        return self.delegate.is_ready()

    def close(self) -> None:
        self.delegate.close()


def _tagged_engine(url: str, tag: str) -> Engine:
    tagged_url = make_url(url).update_query_dict({'application_name': tag})
    settings = Settings(
        database_backend='postgresql',
        database_url=tagged_url.render_as_string(hide_password=False),
        postgres_pool_size=1,
        postgres_max_overflow=0,
        postgres_lock_timeout_ms=10_000,
        postgres_statement_timeout_ms=15_000,
    )
    return create_database_engine(settings)


def _lock_snapshot(
    engine: Engine, a_tag: str, blocker_tag: str
) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                'SELECT pid, application_name, wait_event_type, wait_event, '
                'pg_blocking_pids(pid) AS blockers FROM pg_stat_activity '
                'WHERE application_name IN (:a_tag, :blocker_tag)'
            ),
            {'a_tag': a_tag, 'blocker_tag': blocker_tag},
        ).mappings()
        return [dict(row) for row in rows]


def _observe_lock(
    engine: Engine, a_tag: str, blocker_tag: str
) -> tuple[int, int, list[dict[str, Any]]]:
    deadline = monotonic() + LOCK_OBSERVATION_SECONDS
    snapshot: list[dict[str, Any]] = []
    while monotonic() < deadline:
        snapshot = _lock_snapshot(engine, a_tag, blocker_tag)
        a = next(
            (row for row in snapshot if row['application_name'] == a_tag), None
        )
        blocker = next(
            (
                row
                for row in snapshot
                if row['application_name'] == blocker_tag
            ),
            None,
        )
        if (
            a is not None
            and blocker is not None
            and a['wait_event_type'] == 'Lock'
            and blocker['pid'] in a['blockers']
        ):
            return int(a['pid']), int(blocker['pid']), snapshot
        Event().wait(0.02)
    pytest.fail(f'PostgreSQL lock wait not observed: {snapshot!r}')


def _publish_with_pause(
    resources: RaceResources,
    factory: SessionFactory,
    confirmed: Event,
    release: Event,
) -> int:
    broker = PauseAfterConfirmBroker(resources, confirmed, release)
    try:
        return _publisher(factory, broker).process_batch()
    finally:
        broker.close()


def _participant_errors(futures: list[Future[Any]]) -> list[str]:
    errors = []
    for future in futures:
        try:
            error = future.exception(timeout=WAIT_SECONDS)
        except Exception as error:
            errors.append(repr(error))
        else:
            if error is not None:
                errors.append(repr(error))
    return errors


# Explicit participants and checkpoints keep this proof auditable.
def test_stale_requeue_cannot_reactivate_confirmed_publication(  # noqa: PLR0914, PLR0915
    race_resources: RaceResources,
    record_property: Callable[[str, object], None],
) -> None:
    document, original = _seed_exhausted(race_resources)
    suffix = uuid4().hex[:12]
    a_tag = f'docpipe-b3-a-{suffix}'
    worker_tag = f'docpipe-b3-worker-{suffix}'
    a_engine = _tagged_engine(race_resources.database_url, a_tag)
    worker_engine = _tagged_engine(race_resources.database_url, worker_tag)
    a_factory = create_session_factory(a_engine)
    worker_factory = create_session_factory(worker_engine)
    read = Event()
    release_read = Event()
    updating = Event()
    confirmed = Event()
    release_worker = Event()
    stale = RequeueOutboxEvent(
        unit_of_work_factory=lambda: PauseGetUnitOfWork(
            a_factory, read, release_read, updating
        ),
        max_attempts=MAX_ATTEMPTS,
    )
    futures: list[Future[Any]] = []
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            try:  # noqa: PLW0717
                stale_future = executor.submit(stale.execute, original.id)
                futures.append(stale_future)
                assert read.wait(WAIT_SECONDS), (
                    'stale requeue read not reached'
                )
                _requeue(race_resources.factory).execute(original.id)
                reset_document, reset_event = _read(
                    race_resources, original.id, document.id
                )
                assert reset_document.status is DocumentStatus.STORED
                assert reset_event.attempts == 0
                assert reset_event.last_error == 'synthetic timeout'
                assert reset_event.next_attempt_at is None
                assert reset_event.payload == original.payload
                worker_future = executor.submit(
                    _publish_with_pause,
                    race_resources,
                    worker_factory,
                    confirmed,
                    release_worker,
                )
                futures.append(worker_future)
                assert confirmed.wait(WAIT_SECONDS), (
                    'broker confirm not reached'
                )
                _assert_message(race_resources, original)
                release_read.set()
                assert updating.wait(WAIT_SECONDS), (
                    'conditional UPDATE not reached'
                )
                with pytest.raises(
                    OutboxEventNotRequeueableError,
                    match='changed during requeue',
                ):
                    stale_future.result(timeout=WAIT_SECONDS)
                before_commit_document, before_commit_event = _read(
                    race_resources, original.id, document.id
                )
                assert before_commit_document.status is DocumentStatus.STORED
                assert before_commit_event.published_at is None
                assert before_commit_event.attempts == 0
            except BaseException:
                record_property(
                    'failure_lock_snapshot',
                    repr(
                        _lock_snapshot(
                            race_resources.engine, a_tag, worker_tag
                        )
                    ),
                )
                raise
            finally:
                release_read.set()
                release_worker.set()
                record_property(
                    'participant_errors', repr(_participant_errors(futures))
                )
            assert worker_future.result(timeout=WAIT_SECONDS) == 1
        _assert_published(race_resources, original)
        followup_broker = _broker(race_resources)
        try:
            assert (
                _publisher(worker_factory, followup_broker).process_batch()
                == 0
            )
        finally:
            followup_broker.close()
        record_property(
            'order',
            'stale_read;reset_commit;broker_confirm;conditional_update;'
            'stale_rejected;worker_commit',
        )
    finally:
        release_read.set()
        release_worker.set()
        a_engine.dispose()
        worker_engine.dispose()


def test_concurrent_requeues_observe_row_lock_and_recheck_condition(  # noqa: PLR0914, PLR0915
    race_resources: RaceResources,
    record_property: Callable[[str, object], None],
) -> None:
    document, original = _seed_exhausted(race_resources)
    suffix = uuid4().hex[:12]
    a_tag = f'docpipe-b3-a-{suffix}'
    b_tag = f'docpipe-b3-b-{suffix}'
    a_engine = _tagged_engine(race_resources.database_url, a_tag)
    b_engine = _tagged_engine(race_resources.database_url, b_tag)
    read = Event()
    release_read = Event()
    updating = Event()
    updated = Event()
    release_commit = Event()
    a = RequeueOutboxEvent(
        unit_of_work_factory=lambda: PauseGetUnitOfWork(
            create_session_factory(a_engine), read, release_read, updating
        ),
        max_attempts=MAX_ATTEMPTS,
    )
    b = RequeueOutboxEvent(
        unit_of_work_factory=lambda: PauseCommitUnitOfWork(
            create_session_factory(b_engine), updated, release_commit
        ),
        max_attempts=MAX_ATTEMPTS,
    )
    futures: list[Future[Any]] = []
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            try:  # noqa: PLW0717
                a_future = executor.submit(a.execute, original.id)
                futures.append(a_future)
                assert read.wait(WAIT_SECONDS), 'requeue A read not reached'
                b_future = executor.submit(b.execute, original.id)
                futures.append(b_future)
                assert updated.wait(WAIT_SECONDS), (
                    'requeue B UPDATE not reached'
                )
                release_read.set()
                assert updating.wait(WAIT_SECONDS), (
                    'requeue A conditional UPDATE not reached'
                )
                a_pid, b_pid, snapshot = _observe_lock(
                    race_resources.engine, a_tag, b_tag
                )
                record_property('lock_wait', f'{a_pid} blocked by {b_pid}')
                record_property('lock_snapshot', repr(snapshot))
                before_document, before_event = _read(
                    race_resources, original.id, document.id
                )
                assert before_document.status is DocumentStatus.STORED
                assert before_event.attempts == MAX_ATTEMPTS
                assert before_event.published_at is None
            except BaseException:
                record_property(
                    'failure_lock_snapshot',
                    repr(_lock_snapshot(race_resources.engine, a_tag, b_tag)),
                )
                raise
            finally:
                release_read.set()
                release_commit.set()
                record_property(
                    'participant_errors', repr(_participant_errors(futures))
                )
            b_future.result(timeout=WAIT_SECONDS)
            with pytest.raises(
                OutboxEventNotRequeueableError,
                match='changed during requeue',
            ):
                a_future.result(timeout=WAIT_SECONDS)
        reset_document, reset_event = _read(
            race_resources, original.id, document.id
        )
        assert reset_document.status is DocumentStatus.STORED
        assert reset_event.id == original.id
        assert reset_event.aggregate_id == original.aggregate_id
        assert reset_event.payload == original.payload
        assert reset_event.attempts == 0
        assert reset_event.last_error == 'synthetic timeout'
        assert reset_event.next_attempt_at is None
        assert reset_event.published_at is None
        broker = _broker(race_resources)
        try:
            assert (
                _publisher(race_resources.factory, broker).process_batch() == 1
            )
        finally:
            broker.close()
        _assert_published(race_resources, original)
        _assert_message(race_resources, original)
        record_property(
            'order',
            'a_read;b_update;a_lock_wait;b_commit;a_rejected;broker_confirm;'
            'worker_commit',
        )
    finally:
        release_read.set()
        release_commit.set()
        a_engine.dispose()
        b_engine.dispose()
