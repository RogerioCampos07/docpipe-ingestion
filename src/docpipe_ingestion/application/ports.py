from collections.abc import Iterable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from docpipe_ingestion.domain.models import Document, OutboxEvent


class BinarySource(Protocol):
    """Minimal readable stream accepted by the ingestion use case."""

    def read(self, size: int, /) -> bytes: ...


class DocumentStorage(Protocol):
    """Storage operations independent of the local filesystem."""

    def store(self, storage_key: str, chunks: Iterable[bytes]) -> None: ...

    def list_keys(self) -> set[str]: ...

    def list_incomplete(self, *, older_than: datetime) -> set[str]: ...


class DocumentRepository(Protocol):
    """Persistence operations required for document metadata."""

    def add(self, document: Document) -> None: ...

    def get(self, document_id: UUID) -> Document | None: ...

    def contains_storage_key(self, storage_key: str) -> bool: ...

    def list_storage_keys(self) -> set[str]: ...


class OutboxEventRepository(Protocol):
    """Persistence operations required for outbox events."""

    def add(self, event: OutboxEvent) -> None: ...

    def get(self, event_id: UUID) -> OutboxEvent | None: ...


class UnitOfWork(Protocol):
    """Atomic persistence boundary for ingestion metadata."""

    @property
    def documents(self) -> DocumentRepository: ...

    @property
    def outbox_events(self) -> OutboxEventRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
