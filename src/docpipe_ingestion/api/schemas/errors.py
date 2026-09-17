from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    """Stable, non-sensitive description of an HTTP failure."""

    code: str
    message: str
    correlation_id: UUID


class ErrorResponse(BaseModel):
    """Common envelope returned for expected and unexpected API errors."""

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'error': {
                        'code': 'invalid_request',
                        'message': 'The request is not valid.',
                        'correlation_id': (
                            '87654321-4321-8765-4321-876543218765'
                        ),
                    }
                }
            ]
        }
    )

    error: ErrorDetail
