from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Form, status

from docpipe_ingestion.api.dependencies import (
    GetDocumentUseCase,
    IngestDocumentUseCase,
    get_correlation_id,
    get_document,
    get_ingest_document,
    require_single_document_file,
)
from docpipe_ingestion.api.schemas.documents import (
    DocumentAcceptedResponse,
    DocumentResponse,
    DocumentUploadRequest,
)
from docpipe_ingestion.api.schemas.errors import ErrorResponse
from docpipe_ingestion.application.ingest_document import IngestDocumentCommand

router = APIRouter(prefix='/v1/documents', tags=['documents'])


def _error_response(description: str) -> dict[str, Any]:
    return {'model': ErrorResponse, 'description': description}


@router.post(
    '',
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentAcceptedResponse,
    summary='Ingest one document',
    description=(
        'Accepts one PDF, PNG, or JPEG file. Validation, hashing, storage, '
        'and metadata persistence complete before the acknowledgement.'
    ),
    responses={
        400: _error_response('The multipart request or file is invalid.'),
        413: _error_response('The configured file-size limit was exceeded.'),
        415: _error_response('The file type is not supported.'),
        503: _error_response('Storage or persistence is unavailable.'),
    },
)
def create_document(
    _single_file: Annotated[
        None,
        Depends(require_single_document_file),
    ],
    upload: Annotated[
        DocumentUploadRequest,
        Form(media_type='multipart/form-data'),
    ],
    correlation_id: Annotated[UUID, Depends(get_correlation_id)],
    use_case: Annotated[
        IngestDocumentUseCase,
        Depends(get_ingest_document),
    ],
) -> DocumentAcceptedResponse:
    """Adapt one multipart upload to the infrastructure-free use case."""
    document = use_case.execute(
        IngestDocumentCommand(
            source=upload.file.file,
            original_name=upload.file.filename or '',
            content_type=upload.file.content_type or '',
            correlation_id=correlation_id,
        )
    )
    return DocumentAcceptedResponse.from_document(document)


@router.get(
    '/{document_id}',
    response_model=DocumentResponse,
    summary='Get document metadata',
    description=(
        'Returns only metadata owned by the Ingestion service. The binary '
        'file and storage location are never exposed.'
    ),
    responses={
        400: _error_response('The document identifier is not a valid UUID.'),
        404: _error_response('The document does not exist.'),
        503: _error_response('Metadata persistence is unavailable.'),
    },
)
def read_document(
    document_id: UUID,
    use_case: Annotated[GetDocumentUseCase, Depends(get_document)],
) -> DocumentResponse:
    """Return the public projection of persisted document metadata."""
    return DocumentResponse.from_document(use_case.execute(document_id))
