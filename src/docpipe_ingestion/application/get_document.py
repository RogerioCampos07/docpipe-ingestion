from collections.abc import Callable
from uuid import UUID

from opentelemetry.sdk.trace import TracerProvider

from docpipe_ingestion.application.errors import (
    DocumentNotFoundError,
    MetadataQueryError,
)
from docpipe_ingestion.application.ports import UnitOfWork
from docpipe_ingestion.domain.models import Document
from docpipe_ingestion.infrastructure.observability.tracing import span

type UnitOfWorkFactory = Callable[[], UnitOfWork]


class GetDocument:
    """Retrieve document metadata without exposing persistence details."""

    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        tracer_provider: TracerProvider | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._tracer_provider = tracer_provider

    def execute(self, document_id: UUID) -> Document:
        """Return one document or report a stable application error."""
        try:
            with span('document.get', provider=self._tracer_provider):
                with self._unit_of_work_factory() as unit_of_work:
                    document = unit_of_work.documents.get(document_id)
        except Exception as error:
            raise MetadataQueryError(
                'document metadata query failed'
            ) from error
        if document is None:
            raise DocumentNotFoundError('document does not exist')
        return document
