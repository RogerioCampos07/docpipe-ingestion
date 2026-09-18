import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

from opentelemetry.sdk.trace import TracerProvider

from docpipe_ingestion.application.errors import MetadataPersistenceError
from docpipe_ingestion.application.events import DocumentReceivedV1
from docpipe_ingestion.application.file_validation import (
    ValidatedFileStream,
    sanitize_original_name,
)
from docpipe_ingestion.application.ports import (
    BinarySource,
    DocumentStorage,
    UnitOfWork,
)
from docpipe_ingestion.domain.models import (
    Document,
    DocumentStatus,
    OutboxEvent,
    ensure_utc,
)
from docpipe_ingestion.infrastructure.observability.metrics import Metrics
from docpipe_ingestion.infrastructure.observability.tracing import (
    current_trace_context,
    span,
)

type UnitOfWorkFactory = Callable[[], UnitOfWork]
type Clock = Callable[[], datetime]
type UUIDFactory = Callable[[], UUID]
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestDocumentCommand:
    """Infrastructure-independent input for one document ingestion."""

    source: BinarySource
    original_name: str
    content_type: str
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class IngestionLimits:
    """Memory and file-size limits applied during ingestion."""

    max_size_bytes: int
    chunk_size_bytes: int


def utc_now() -> datetime:
    """Return the current aware UTC time."""
    return datetime.now(UTC)


class IngestDocument:
    """Validate, store, and persist metadata for one document."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        storage: DocumentStorage,
        unit_of_work_factory: UnitOfWorkFactory,
        limits: IngestionLimits,
        clock: Clock = utc_now,
        uuid_factory: UUIDFactory = uuid4,
        metrics: Metrics | None = None,
        tracer_provider: TracerProvider | None = None,
        storage_backend: str = 'local',
    ) -> None:
        self._storage = storage
        self._unit_of_work_factory = unit_of_work_factory
        self._limits = limits
        self._clock = clock
        self._uuid_factory = uuid_factory
        self._metrics = metrics
        self._tracer_provider = tracer_provider
        self._storage_backend = storage_backend

    def execute(self, command: IngestDocumentCommand) -> Document:
        """Run the ingestion flow without exposing an HTTP contract."""
        started = perf_counter()
        with span(
            'document.ingest',
            provider=self._tracer_provider,
            attributes={'docpipe.correlation_id': str(command.correlation_id)},
        ):
            return self._execute(command, started)

    def _execute(
        self, command: IngestDocumentCommand, started: float
    ) -> Document:
        original_name = sanitize_original_name(command.original_name)
        document_id = self._uuid_factory()
        storage_key = f'{self._uuid_factory().hex}.blob'
        validated_stream = ValidatedFileStream(
            command.source,
            original_name=original_name,
            content_type=command.content_type,
            max_size_bytes=self._limits.max_size_bytes,
            chunk_size_bytes=self._limits.chunk_size_bytes,
        )

        storage_started = perf_counter()
        try:
            with span('storage.upload', provider=self._tracer_provider):
                self._storage.store(storage_key, validated_stream)
        except Exception as error:
            if self._metrics is not None:
                self._metrics.storage_duration.labels(
                    self._storage_backend, 'failure'
                ).observe(perf_counter() - storage_started)
                self._metrics.storage_errors.labels(
                    self._storage_backend, 'upload', type(error).__name__
                ).inc()
                self._metrics.uploads.labels('failed').inc()
            logger.warning(
                'storage upload failed',
                extra={
                    'operation': 'storage.upload',
                    'status': 'failure',
                    'duration_ms': round(
                        (perf_counter() - storage_started) * 1000, 3
                    ),
                    'dependency_type': 'storage',
                    'dependency_backend': self._storage_backend,
                    'error_category': type(error).__name__,
                },
            )
            raise
        file_metadata = validated_stream.metadata
        logger.info(
            'storage upload completed',
            extra={
                'operation': 'storage.upload',
                'status': 'success',
                'duration_ms': round(
                    (perf_counter() - storage_started) * 1000, 3
                ),
                'dependency_type': 'storage',
                'dependency_backend': self._storage_backend,
            },
        )
        occurred_at = ensure_utc(self._clock(), field_name='clock')
        document = Document(
            id=document_id,
            original_name=original_name,
            media_type=file_metadata.media_type,
            size_bytes=file_metadata.size_bytes,
            sha256=file_metadata.sha256,
            storage_key=storage_key,
            status=DocumentStatus.STORED,
            correlation_id=command.correlation_id,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        event_id = self._uuid_factory()
        event_payload = DocumentReceivedV1.from_document(
            document,
            event_id=event_id,
        )
        event = OutboxEvent(
            id=event_id,
            aggregate_id=document_id,
            event_type='document.received.v1',
            payload=event_payload.model_dump(mode='json'),
            created_at=occurred_at,
            trace_context=current_trace_context(),
        )

        try:
            with self._unit_of_work_factory() as unit_of_work:
                unit_of_work.documents.add(document)
                unit_of_work.outbox_events.add(event)
                unit_of_work.commit()
        except Exception as error:
            raise MetadataPersistenceError(storage_key) from error
        if self._metrics is not None:
            self._metrics.storage_duration.labels(
                self._storage_backend, 'success'
            ).observe(perf_counter() - storage_started)
            self._metrics.storage_bytes.labels(self._storage_backend).inc(
                file_metadata.size_bytes
            )
            self._metrics.documents_accepted.inc()
            self._metrics.uploads.labels('accepted').inc()
        logger.info(
            'document ingestion completed',
            extra={
                'operation': 'document.ingest',
                'status': 'accepted',
                'duration_ms': round((perf_counter() - started) * 1000, 3),
            },
        )
        return document
