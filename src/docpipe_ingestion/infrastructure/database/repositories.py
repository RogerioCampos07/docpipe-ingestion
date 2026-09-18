from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
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
        next_attempt_at=model.next_attempt_at,
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
                next_attempt_at=event.next_attempt_at,
            )
        )

    def get(self, event_id: UUID) -> OutboxEvent | None:
        model = self._session.get(OutboxEventModel, event_id)
        return None if model is None else _to_outbox_event(model)

    def list_pending(
        self,
        *,
        limit: int,
        max_attempts: int,
        eligible_at: datetime | None = None,
        lock: bool = False,
    ) -> list[OutboxEvent]:
        statement = (
            select(OutboxEventModel)
            .where(OutboxEventModel.published_at.is_(None))
            .where(OutboxEventModel.attempts < max_attempts)
            .order_by(OutboxEventModel.created_at, OutboxEventModel.id)
            .limit(limit)
        )
        if eligible_at is not None:
            statement = statement.where(
                (OutboxEventModel.next_attempt_at.is_(None))
                | (OutboxEventModel.next_attempt_at <= eligible_at)
            )
        if lock:
            statement = statement.with_for_update(skip_locked=True)
        models = self._session.scalars(statement)
        return [_to_outbox_event(model) for model in models]

    def record_failure(
        self,
        event_id: UUID,
        error: str,
        *,
        next_attempt_at: datetime | None = None,
    ) -> None:
        self._session.execute(
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .where(OutboxEventModel.published_at.is_(None))
            .values(
                attempts=OutboxEventModel.attempts + 1,
                last_error=error[:500],
                next_attempt_at=next_attempt_at,
            )
        )

    def mark_published(self, event_id: UUID, published_at: datetime) -> None:
        event = self._session.get(OutboxEventModel, event_id)
        if event is None or event.published_at is not None:
            return
        event.attempts += 1
        event.last_error = None
        event.published_at = published_at
        event.next_attempt_at = None
        self._session.execute(
            update(DocumentModel)
            .where(DocumentModel.id == event.aggregate_id)
            .where(DocumentModel.status == 'STORED')
            .values(status='PUBLISHED', updated_at=published_at)
        )
