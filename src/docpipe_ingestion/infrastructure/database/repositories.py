from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from docpipe_ingestion.domain.models import (
    Document,
    JsonValue,
    OutboxEvent,
)
from docpipe_ingestion.infrastructure.database.models import (
    DocumentModel,
    OutboxEventModel,
)


def _to_document(model: DocumentModel) -> Document:
    return Document(
        id=model.id,
        original_name=model.original_name,
        media_type=model.media_type,
        size_bytes=model.size_bytes,
        sha256=model.sha256,
        storage_key=model.storage_key,
        status=model.status,
        correlation_id=model.correlation_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_outbox_event(model: OutboxEventModel) -> OutboxEvent:
    payload = cast(dict[str, JsonValue], model.payload)
    return OutboxEvent(
        id=model.id,
        aggregate_id=model.aggregate_id,
        event_type=model.event_type,
        payload=payload,
        created_at=model.created_at,
        published_at=model.published_at,
        attempts=model.attempts,
        last_error=model.last_error,
    )


class SqlAlchemyDocumentRepository:
    """Store document metadata in a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, document: Document) -> None:
        self._session.add(
            DocumentModel(
                id=document.id,
                original_name=document.original_name,
                media_type=document.media_type,
                size_bytes=document.size_bytes,
                sha256=document.sha256,
                storage_key=document.storage_key,
                status=document.status,
                correlation_id=document.correlation_id,
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
        )

    def get(self, document_id: UUID) -> Document | None:
        model = self._session.get(DocumentModel, document_id)
        return None if model is None else _to_document(model)

    def contains_storage_key(self, storage_key: str) -> bool:
        statement = select(DocumentModel.id).where(
            DocumentModel.storage_key == storage_key
        )
        return self._session.scalar(statement) is not None

    def list_storage_keys(self) -> set[str]:
        return set(self._session.scalars(select(DocumentModel.storage_key)))


class SqlAlchemyOutboxEventRepository:
    """Store outbox events in the same SQLAlchemy session as documents."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: OutboxEvent) -> None:
        self._session.add(
            OutboxEventModel(
                id=event.id,
                aggregate_id=event.aggregate_id,
                event_type=event.event_type,
                payload=event.payload,
                created_at=event.created_at,
                published_at=event.published_at,
                attempts=event.attempts,
                last_error=event.last_error,
            )
        )

    def get(self, event_id: UUID) -> OutboxEvent | None:
        model = self._session.get(OutboxEventModel, event_id)
        return None if model is None else _to_outbox_event(model)
