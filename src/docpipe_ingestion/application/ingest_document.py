from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from docpipe_ingestion.application.errors import MetadataPersistenceError
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

type UnitOfWorkFactory = Callable[[], UnitOfWork]
type Clock = Callable[[], datetime]
type UUIDFactory = Callable[[], UUID]


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

    def __init__(
        self,
        *,
        storage: DocumentStorage,
        unit_of_work_factory: UnitOfWorkFactory,
        limits: IngestionLimits,
        clock: Clock = utc_now,
        uuid_factory: UUIDFactory = uuid4,
    ) -> None:
        self._storage = storage
        self._unit_of_work_factory = unit_of_work_factory
        self._limits = limits
        self._clock = clock
        self._uuid_factory = uuid_factory

    def execute(self, command: IngestDocumentCommand) -> Document:
        """Run the ingestion flow without exposing an HTTP contract."""
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

        self._storage.store(storage_key, validated_stream)
        file_metadata = validated_stream.metadata
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
        event = OutboxEvent(
            id=event_id,
            aggregate_id=document_id,
            event_type='document.received.v1',
            payload={
                'event_id': str(event_id),
                'event_type': 'document.received',
                'event_version': 1,
                'occurred_at': occurred_at.isoformat(),
                'correlation_id': str(command.correlation_id),
                'document_id': str(document_id),
                'data': {
                    'storage_key': storage_key,
                    'media_type': file_metadata.media_type,
                    'size_bytes': file_metadata.size_bytes,
                    'sha256': file_metadata.sha256,
                },
            },
            created_at=occurred_at,
        )

        try:
            with self._unit_of_work_factory() as unit_of_work:
                unit_of_work.documents.add(document)
                unit_of_work.outbox_events.add(event)
                unit_of_work.commit()
        except Exception as error:
            raise MetadataPersistenceError(storage_key) from error
        return document
