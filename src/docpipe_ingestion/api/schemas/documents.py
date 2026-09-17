from datetime import datetime
from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field

from docpipe_ingestion.domain.models import Document, DocumentStatus

_DOCUMENT_ID = '12345678-1234-5678-1234-567812345678'
_CORRELATION_ID = '87654321-4321-8765-4321-876543218765'
_OCCURRED_AT = '2026-09-17T12:00:00Z'


class DocumentUploadRequest(BaseModel):
    """Multipart fields accepted by the first document API version."""

    model_config = ConfigDict(extra='forbid')

    file: UploadFile = Field(
        description='One PDF, PNG, or JPEG document.',
    )


class DocumentAcceptedResponse(BaseModel):
    """Acknowledgement returned after safe document acceptance."""

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'document_id': _DOCUMENT_ID,
                    'status': 'STORED',
                    'correlation_id': _CORRELATION_ID,
                    'received_at': _OCCURRED_AT,
                }
            ]
        }
    )

    document_id: UUID
    status: DocumentStatus
    correlation_id: UUID
    received_at: datetime

    @classmethod
    def from_document(cls, document: Document) -> DocumentAcceptedResponse:
        return cls(
            document_id=document.id,
            status=document.status,
            correlation_id=document.correlation_id,
            received_at=document.created_at,
        )


class DocumentResponse(BaseModel):
    """Ingestion-owned metadata exposed by the document query."""

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'document_id': _DOCUMENT_ID,
                    'original_name': 'sample.pdf',
                    'media_type': 'application/pdf',
                    'size_bytes': 12345,
                    'sha256': 'a' * 64,
                    'status': 'STORED',
                    'correlation_id': _CORRELATION_ID,
                    'created_at': _OCCURRED_AT,
                    'updated_at': _OCCURRED_AT,
                }
            ]
        }
    )

    document_id: UUID
    original_name: str
    media_type: str
    size_bytes: int
    sha256: str
    status: DocumentStatus
    correlation_id: UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, document: Document) -> DocumentResponse:
        return cls(
            document_id=document.id,
            original_name=document.original_name,
            media_type=document.media_type,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            status=document.status,
            correlation_id=document.correlation_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
