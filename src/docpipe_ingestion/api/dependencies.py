from dataclasses import dataclass
from threading import Lock
from typing import Protocol, cast
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import Engine

from docpipe_ingestion.application.errors import (
    MetadataQueryError,
    StorageError,
)
from docpipe_ingestion.application.get_document import GetDocument
from docpipe_ingestion.application.ingest_document import (
    IngestDocument,
    IngestDocumentCommand,
    IngestionLimits,
)
from docpipe_ingestion.application.ports import DocumentStorage
from docpipe_ingestion.domain.models import Document
from docpipe_ingestion.infrastructure.composition import (
    create_document_storage,
)
from docpipe_ingestion.infrastructure.database.engine import (
    SessionFactory,
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from docpipe_ingestion.infrastructure.settings import Settings


class IngestDocumentUseCase(Protocol):
    """API-facing contract for document ingestion."""

    def execute(self, command: IngestDocumentCommand) -> Document: ...


class GetDocumentUseCase(Protocol):
    """API-facing contract for document metadata queries."""

    def execute(self, document_id: UUID) -> Document: ...


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    """Long-lived resources and use cases owned by one API instance."""

    ingest_document: IngestDocumentUseCase
    get_document: GetDocumentUseCase


class ApplicationServiceProvider:
    """Create document services lazily while keeping liveness independent."""

    def __init__(
        self,
        settings: Settings,
        services: ApplicationServices | None = None,
    ) -> None:
        self._settings = settings
        self._services = services
        self._owns_services = services is None
        self._lock = Lock()
        self._engine: Engine | None = None
        self._session_factory: SessionFactory | None = None
        self._ingest_document: IngestDocumentUseCase | None = None
        self._get_document: GetDocumentUseCase | None = None
        self._storage: DocumentStorage | None = None

    def _ensure_database(self) -> None:
        if self._session_factory is not None:
            return
        self._engine = create_database_engine(self._settings)
        self._session_factory = create_session_factory(self._engine)

    def _unit_of_work_factory(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(
            cast(SessionFactory, self._session_factory)
        )

    def ingest_document(self) -> IngestDocumentUseCase:
        if self._services is not None:
            return self._services.ingest_document
        with self._lock:
            if self._ingest_document is None:
                self._ensure_database()
                storage = create_document_storage(self._settings)
                self._storage = storage
                self._ingest_document = IngestDocument(
                    storage=storage,
                    unit_of_work_factory=self._unit_of_work_factory,
                    limits=IngestionLimits(
                        max_size_bytes=self._settings.max_file_size_bytes,
                        chunk_size_bytes=(
                            self._settings.storage_chunk_size_bytes
                        ),
                    ),
                )
        return self._ingest_document

    def get_document(self) -> GetDocumentUseCase:
        if self._services is not None:
            return self._services.get_document
        with self._lock:
            if self._get_document is None:
                self._ensure_database()
                self._get_document = GetDocument(self._unit_of_work_factory)
        return self._get_document

    def close(self) -> None:
        if not self._owns_services:
            return
        if self._engine is not None:
            self._engine.dispose()
        close = getattr(self._storage, 'close', None)
        if close is not None:
            close()


def _get_service_provider(request: Request) -> ApplicationServiceProvider:
    return cast(
        ApplicationServiceProvider,
        request.app.state.service_provider,
    )


def get_ingest_document(request: Request) -> IngestDocumentUseCase:
    provider = _get_service_provider(request)
    try:
        return provider.ingest_document()
    except StorageError:
        raise
    except Exception as error:
        raise MetadataQueryError(
            'application dependencies are unavailable'
        ) from error


def get_document(request: Request) -> GetDocumentUseCase:
    provider = _get_service_provider(request)
    try:
        return provider.get_document()
    except Exception as error:
        raise MetadataQueryError(
            'application dependencies are unavailable'
        ) from error


def get_correlation_id(request: Request) -> UUID:
    return cast(UUID, request.state.correlation_id)


async def require_single_document_file(request: Request) -> None:
    """Reject repeated file fields before invoking the ingestion use case."""
    form = await request.form()
    if len(form.getlist('file')) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='exactly one file is required',
        )
