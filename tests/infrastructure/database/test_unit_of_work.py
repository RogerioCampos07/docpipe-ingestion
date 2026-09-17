from contextlib import ExitStack
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from docpipe_ingestion.domain.models import OutboxEvent
from docpipe_ingestion.infrastructure.database.engine import SessionFactory
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)


def _commit_event_without_document(
    session_factory: SessionFactory,
    event: OutboxEvent,
) -> None:
    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        unit_of_work.outbox_events.add(event)
        unit_of_work.commit()


def test_foreign_key_rejects_event_without_document(
    session_factory: SessionFactory,
) -> None:
    missing_document_id = UUID('12345678-1234-5678-1234-567812345678')
    event = OutboxEvent(
        id=UUID('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'),
        aggregate_id=missing_document_id,
        event_type='test.event',
        payload={},
        created_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
    )

    with pytest.raises(IntegrityError):
        _commit_event_without_document(session_factory, event)


def test_unit_of_work_requires_an_active_context(
    session_factory: SessionFactory,
) -> None:
    unit_of_work = SqlAlchemyUnitOfWork(session_factory)

    with pytest.raises(RuntimeError, match='not been entered'):
        _ = unit_of_work.documents
    with pytest.raises(RuntimeError, match='not been entered'):
        _ = unit_of_work.outbox_events
    with pytest.raises(RuntimeError, match='not been entered'):
        unit_of_work.commit()
    with pytest.raises(RuntimeError, match='not been entered'):
        unit_of_work.rollback()
    unit_of_work.__exit__(None, None, None)


def test_unit_of_work_cannot_be_entered_twice(
    session_factory: SessionFactory,
) -> None:
    unit_of_work = SqlAlchemyUnitOfWork(session_factory)

    with ExitStack() as stack:
        stack.enter_context(unit_of_work)
        unit_of_work.rollback()
        with pytest.raises(RuntimeError, match='entered twice'):
            stack.enter_context(unit_of_work)
