"""Requeue one exhausted outbox event for the worker."""

import argparse
from functools import partial
from uuid import UUID

from docpipe_ingestion.application.errors import (
    OutboxEventNotFoundError,
    OutboxEventNotRequeueableError,
)
from docpipe_ingestion.application.requeue_outbox_event import (
    RequeueOutboxEvent,
)
from docpipe_ingestion.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from docpipe_ingestion.infrastructure.observability.logging import (
    configure_logging,
)
from docpipe_ingestion.infrastructure.settings import Settings


def requeue(event_id: UUID, settings: Settings) -> None:
    """Atomically make an exhausted event eligible for publication again."""
    configure_logging(settings)
    engine = create_database_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        use_case = RequeueOutboxEvent(
            unit_of_work_factory=partial(
                SqlAlchemyUnitOfWork,
                session_factory,
                backend=settings.database_backend,
            ),
            max_attempts=settings.outbox_max_attempts,
        )
        use_case.execute(event_id)
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('event_id', type=UUID)
    arguments = parser.parse_args()
    try:
        requeue(arguments.event_id, Settings())
    except (
        OutboxEventNotFoundError,
        OutboxEventNotRequeueableError,
    ) as error:
        parser.exit(1, f'{error}\n')
    print(f'outbox event requeued: {arguments.event_id}')


if __name__ == '__main__':
    main()
