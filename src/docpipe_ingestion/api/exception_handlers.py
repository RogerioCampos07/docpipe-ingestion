from uuid import UUID, uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from docpipe_ingestion.api.schemas.errors import ErrorDetail, ErrorResponse
from docpipe_ingestion.application.errors import (
    DocumentNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    InvalidFileMetadataError,
    MetadataPersistenceError,
    MetadataQueryError,
    StorageError,
    UnsupportedFileTypeError,
)

CORRELATION_HEADER = 'X-Correlation-ID'


def request_correlation_id(request: Request) -> UUID:
    correlation_id = getattr(request.state, 'correlation_id', None)
    if isinstance(correlation_id, UUID):
        return correlation_id
    correlation_id = uuid4()
    request.state.correlation_id = correlation_id
    return correlation_id


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    """Build the single public error shape without internal details."""
    correlation_id = request_correlation_id(request)
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            correlation_id=correlation_id,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode='json'),
        headers={CORRELATION_HEADER: str(correlation_id)},
    )


def install_exception_handlers(application: FastAPI) -> None:
    """Register centralized mappings from application errors to HTTP."""

    @application.exception_handler(InvalidFileMetadataError)
    async def invalid_metadata(
        request: Request,
        error: InvalidFileMetadataError,
    ) -> JSONResponse:
        del error
        return error_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            code='invalid_file',
            message='The uploaded file metadata is not valid.',
        )

    @application.exception_handler(EmptyFileError)
    async def empty_file(
        request: Request,
        error: EmptyFileError,
    ) -> JSONResponse:
        del error
        return error_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            code='empty_file',
            message='The uploaded file cannot be empty.',
        )

    @application.exception_handler(FileTooLargeError)
    async def file_too_large(
        request: Request,
        error: FileTooLargeError,
    ) -> JSONResponse:
        del error
        return error_response(
            request,
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            code='file_too_large',
            message='The uploaded file exceeds the configured size limit.',
        )

    @application.exception_handler(UnsupportedFileTypeError)
    async def unsupported_file_type(
        request: Request,
        error: UnsupportedFileTypeError,
    ) -> JSONResponse:
        del error
        return error_response(
            request,
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code='unsupported_file_type',
            message='The uploaded file type is not supported.',
        )

    @application.exception_handler(DocumentNotFoundError)
    async def document_not_found(
        request: Request,
        error: DocumentNotFoundError,
    ) -> JSONResponse:
        del error
        return error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code='document_not_found',
            message='The requested document does not exist.',
        )

    @application.exception_handler(StorageError)
    async def storage_unavailable(
        request: Request,
        error: StorageError,
    ) -> JSONResponse:
        del error
        return error_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code='storage_unavailable',
            message='Document storage is temporarily unavailable.',
        )

    @application.exception_handler(MetadataPersistenceError)
    @application.exception_handler(MetadataQueryError)
    async def persistence_unavailable(
        request: Request,
        error: MetadataPersistenceError | MetadataQueryError,
    ) -> JSONResponse:
        del error
        return error_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code='persistence_unavailable',
            message='Document metadata is temporarily unavailable.',
        )

    @application.exception_handler(RequestValidationError)
    async def invalid_request(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        del error
        return error_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            code='invalid_request',
            message='The request is not valid.',
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error(
        request: Request,
        error: StarletteHTTPException,
    ) -> JSONResponse:
        code = 'invalid_request'
        message = 'The request is not valid.'
        if error.status_code == status.HTTP_404_NOT_FOUND:
            code = 'not_found'
            message = 'The requested resource does not exist.'
        return error_response(
            request,
            status_code=error.status_code,
            code=code,
            message=message,
        )

    @application.exception_handler(Exception)
    async def internal_error(
        request: Request,
        error: Exception,
    ) -> JSONResponse:
        del error
        return error_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code='internal_error',
            message='An unexpected error occurred.',
        )
