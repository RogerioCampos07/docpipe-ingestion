"""Validated event contracts produced by the ingestion service."""

from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from docpipe_ingestion.domain.models import Document, ensure_utc


class DocumentReceivedData(BaseModel):
    """Allowed document metadata in ``document.received.v1``."""

    model_config = ConfigDict(extra='forbid')

    storage_key: str = Field(pattern=r'^[0-9a-f]{32}\.blob$')
    media_type: Literal['application/pdf', 'image/png', 'image/jpeg']
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class DocumentReceivedV1(BaseModel):
    """Version 1 envelope for a safely stored document."""

    model_config = ConfigDict(extra='forbid')

    event_id: UUID
    event_type: Literal['document.received']
    event_version: Literal[1]
    occurred_at: datetime
    correlation_id: UUID
    document_id: UUID
    data: DocumentReceivedData

    @field_validator('occurred_at')
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return ensure_utc(value, field_name='occurred_at')

    @classmethod
    def from_document(
        cls,
        document: Document,
        *,
        event_id: UUID,
    ) -> 'DocumentReceivedV1':
        return cls(
            event_id=event_id,
            event_type='document.received',
            event_version=1,
            occurred_at=document.created_at,
            correlation_id=document.correlation_id,
            document_id=document.id,
            data=DocumentReceivedData(
                storage_key=document.storage_key,
                media_type=cast(
                    Literal['application/pdf', 'image/png', 'image/jpeg'],
                    document.media_type,
                ),
                size_bytes=document.size_bytes,
                sha256=document.sha256,
            ),
        )
