from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from docpipe_ingestion.domain.models import DocumentStatus
from docpipe_ingestion.infrastructure.database.base import Base, UTCDateTime


class DocumentModel(Base):
    """Relational representation of document metadata."""

    __tablename__ = 'documents'
    __table_args__ = (
        CheckConstraint('size_bytes > 0', name='ck_documents_size_positive'),
        CheckConstraint(
            'length(sha256) = 64',
            name='ck_documents_sha256_length',
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=False),
        primary_key=True,
    )
    original_name: Mapped[str] = mapped_column(String, nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name='document_status',
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    correlation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
    )


class OutboxEventModel(Base):
    """Relational representation of a pending or published event."""

    __tablename__ = 'outbox_events'
    __table_args__ = (
        CheckConstraint(
            'attempts >= 0',
            name='ck_outbox_events_attempts_non_negative',
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=False),
        primary_key=True,
    )
    aggregate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=False),
        ForeignKey('documents.id', ondelete='RESTRICT'),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
        nullable=True,
    )
    attempts: Mapped[int] = mapped_column(
        default=0,
        server_default='0',
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
        nullable=True,
        index=True,
    )
    trace_context: Mapped[dict[str, str] | None] = mapped_column(
        JSON, nullable=True
    )
