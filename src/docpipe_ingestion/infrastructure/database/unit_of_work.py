import logging
from time import perf_counter
from types import TracebackType

from opentelemetry.sdk.trace import TracerProvider
from sqlalchemy.orm import Session

from docpipe_ingestion.infrastructure.database.engine import SessionFactory
from docpipe_ingestion.infrastructure.database.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyOutboxEventRepository,
)
from docpipe_ingestion.infrastructure.observability.metrics import Metrics
from docpipe_ingestion.infrastructure.observability.tracing import span

logger = logging.getLogger(__name__)


class SqlAlchemyUnitOfWork:
    """Coordinate repositories in one SQLAlchemy transaction."""

    def __init__(
        self,
        session_factory: SessionFactory,
        metrics: Metrics | None = None,
        backend: str = 'sqlite',
        tracer_provider: TracerProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._documents: SqlAlchemyDocumentRepository | None = None
        self._outbox_events: SqlAlchemyOutboxEventRepository | None = None
        self._metrics = metrics
        self._backend = backend
        self._tracer_provider = tracer_provider

    @property
    def documents(self) -> SqlAlchemyDocumentRepository:
        if self._documents is None:
            raise RuntimeError('unit of work has not been entered')
        return self._documents

    @property
    def outbox_events(self) -> SqlAlchemyOutboxEventRepository:
        if self._outbox_events is None:
            raise RuntimeError('unit of work has not been entered')
        return self._outbox_events

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        if self._session is not None:
            raise RuntimeError('unit of work cannot be entered twice')
        self._session = self._session_factory()
        self._documents = SqlAlchemyDocumentRepository(self._session)
        self._outbox_events = SqlAlchemyOutboxEventRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        if self._session is None:
            return
        try:
            self._session.rollback()
        finally:
            self._session.close()
            self._session = None
            self._documents = None
            self._outbox_events = None

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError('unit of work has not been entered')
        started = perf_counter()
        try:
            with span('database.commit', provider=self._tracer_provider):
                self._session.commit()
        except Exception as error:
            if self._metrics is not None:
                self._metrics.database_errors.labels(
                    self._backend, 'commit', type(error).__name__
                ).inc()
                self._metrics.database_transactions.labels(
                    self._backend, 'write', 'failure'
                ).inc()
                self._metrics.database_duration.labels(
                    self._backend, 'commit', 'failure'
                ).observe(perf_counter() - started)
            logger.warning(
                'database transaction failed',
                extra={
                    'operation': 'database.commit',
                    'status': 'failure',
                    'duration_ms': round((perf_counter() - started) * 1000, 3),
                    'dependency_type': 'database',
                    'dependency_backend': self._backend,
                    'error_category': type(error).__name__,
                },
            )
            raise
        if self._metrics is not None:
            self._metrics.database_transactions.labels(
                self._backend, 'write', 'committed'
            ).inc()
            self._metrics.database_duration.labels(
                self._backend, 'commit', 'success'
            ).observe(perf_counter() - started)
        logger.info(
            'database transaction committed',
            extra={
                'operation': 'database.commit',
                'status': 'success',
                'duration_ms': round((perf_counter() - started) * 1000, 3),
                'dependency_type': 'database',
                'dependency_backend': self._backend,
            },
        )

    def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError('unit of work has not been entered')
        started = perf_counter()
        self._session.rollback()
        if self._metrics is not None:
            self._metrics.database_transactions.labels(
                self._backend, 'explicit', 'rolled_back'
            ).inc()
            self._metrics.database_duration.labels(
                self._backend, 'rollback', 'success'
            ).observe(perf_counter() - started)
