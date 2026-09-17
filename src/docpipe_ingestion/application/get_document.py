from collections.abc import Callable
from uuid import UUID

from docpipe_ingestion.application.errors import (
    DocumentNotFoundError,
    MetadataQueryError,
)
from docpipe_ingestion.application.ports import UnitOfWork
from docpipe_ingestion.domain.models import Document

type UnitOfWorkFactory = Callable[[], UnitOfWork]


class GetDocument:
    """Retrieve document metadata without exposing persistence details."""

    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def execute(self, document_id: UUID) -> Document:
        """Return one document or report a stable application error."""
        try:
            with self._unit_of_work_factory() as unit_of_work:
                document = unit_of_work.documents.get(document_id)
        except Exception as error:
            raise MetadataQueryError(
                'document metadata query failed'
            ) from error
        if document is None:
            raise DocumentNotFoundError('document does not exist')
        return document
