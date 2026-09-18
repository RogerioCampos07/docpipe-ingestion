"""Read-only operational lookup by correlation identifier."""

import argparse
import json
from uuid import UUID

from sqlalchemy import select

from docpipe_ingestion.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.models import (
    DocumentModel,
    OutboxEventModel,
)
from docpipe_ingestion.infrastructure.settings import Settings


def lookup(
    correlation_id: UUID, settings: Settings
) -> list[dict[str, object]]:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        statement = (
            select(DocumentModel, OutboxEventModel)
            .join(
                OutboxEventModel,
                OutboxEventModel.aggregate_id == DocumentModel.id,
            )
            .where(DocumentModel.correlation_id == correlation_id)
        )
        with session_factory() as session:
            rows = session.execute(statement).all()
        return [
            {
                'document_id': str(document.id),
                'document_status': document.status,
                'event_id': str(event.id),
                'event_type': event.event_type,
                'attempts': event.attempts,
                'error_category': event.last_error,
                'created_at': document.created_at.isoformat(),
                'published_at': (
                    event.published_at.isoformat()
                    if event.published_at is not None
                    else None
                ),
            }
            for document, event in rows
        ]
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('correlation_id', type=UUID)
    arguments = parser.parse_args()
    print(json.dumps(lookup(arguments.correlation_id, Settings()), indent=2))


if __name__ == '__main__':
    main()
