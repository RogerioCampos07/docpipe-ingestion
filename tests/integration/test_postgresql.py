import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete

from docpipe_ingestion.domain.models import (
    Document,
    DocumentStatus,
    OutboxEvent,
)
from docpipe_ingestion.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.models import (
    DocumentModel,
    OutboxEventModel,
)
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from docpipe_ingestion.infrastructure.settings import Settings
from tests.integration.conftest import migrate

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(
        os.environ.get('DOCPIPE_POSTGRESQL_INTEGRATION') != '1',
        reason='set DOCPIPE_POSTGRESQL_INTEGRATION=1',
    ),
]


def _settings(url: str) -> Settings:
    return Settings(database_backend='postgresql', database_url=url)


def test_postgresql_migrations_transaction_and_skip_locked(
    postgresql_url: str,
) -> None:
    migrate(postgresql_url)
    engine = create_database_engine(_settings(postgresql_url))
    factory = create_session_factory(engine)
    now = datetime.now(UTC)
    document_id = uuid4()
    event_id = uuid4()
    document = Document(
        id=document_id,
        original_name='synthetic.pdf',
        media_type='application/pdf',
        size_bytes=10,
        sha256='a' * 64,
        storage_key=f'{uuid4().hex}.blob',
        status=DocumentStatus.STORED,
        correlation_id=uuid4(),
        created_at=now,
        updated_at=now,
    )
    event = OutboxEvent(
        id=event_id,
        aggregate_id=document_id,
        event_type='document.received.v1',
        payload={'document_id': str(document_id)},
        created_at=now,
    )
    try:
        with factory.begin() as session:
            session.execute(delete(OutboxEventModel))
            session.execute(delete(DocumentModel))
        with SqlAlchemyUnitOfWork(factory) as unit:
            unit.documents.add(document)
            unit.outbox_events.add(event)
            unit.commit()
        with SqlAlchemyUnitOfWork(factory) as first:
            selected = first.outbox_events.list_pending(
                limit=1,
                max_attempts=5,
                eligible_at=now,
                lock=True,
            )
            assert [item.id for item in selected] == [event_id]
            with SqlAlchemyUnitOfWork(factory) as second:
                assert (
                    second.outbox_events.list_pending(
                        limit=1,
                        max_attempts=5,
                        eligible_at=now,
                        lock=True,
                    )
                    == []
                )
        with SqlAlchemyUnitOfWork(factory) as unit:
            assert unit.documents.get(document_id) == document
    finally:
        engine.dispose()


def test_postgresql_rolls_back_document_and_outbox_together(
    postgresql_url: str,
) -> None:
    migrate(postgresql_url)
    engine = create_database_engine(_settings(postgresql_url))
    factory = create_session_factory(engine)
    document_id = uuid4()
    now = datetime.now(UTC)
    document = Document(
        id=document_id,
        original_name='rollback.pdf',
        media_type='application/pdf',
        size_bytes=8,
        sha256='b' * 64,
        storage_key=f'{uuid4().hex}.blob',
        status=DocumentStatus.STORED,
        correlation_id=uuid4(),
        created_at=now,
        updated_at=now,
    )
    try:
        with SqlAlchemyUnitOfWork(factory) as unit:
            unit.documents.add(document)
        with SqlAlchemyUnitOfWork(factory) as unit:
            assert unit.documents.get(document_id) is None
    finally:
        engine.dispose()
