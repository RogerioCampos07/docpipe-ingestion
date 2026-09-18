"""Independent command for the transactional outbox publisher."""

import logging
import signal
from functools import partial
from threading import Event

from docpipe_ingestion.application.publish_outbox import (
    OutboxPublisher,
    PublisherSettings,
)
from docpipe_ingestion.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from docpipe_ingestion.infrastructure.messaging.rabbitmq import (
    RabbitMQPublisher,
)
from docpipe_ingestion.infrastructure.settings import Settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    settings = Settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    stop_event = Event()

    def stop(signum: int, frame: object) -> None:
        del signum, frame
        stop_event.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    broker = RabbitMQPublisher(
        url=settings.rabbitmq_url,
        exchange=settings.rabbitmq_exchange,
        queue=settings.rabbitmq_queue,
        routing_key=settings.rabbitmq_routing_key,
        timeout_seconds=settings.rabbitmq_timeout_seconds,
    )
    publisher = OutboxPublisher(
        unit_of_work_factory=partial(SqlAlchemyUnitOfWork, session_factory),
        broker=broker,
        settings=PublisherSettings(
            batch_size=settings.outbox_batch_size,
            max_attempts=settings.outbox_max_attempts,
            backoff_seconds=settings.outbox_backoff_seconds,
            polling_seconds=settings.outbox_polling_seconds,
        ),
    )
    try:
        publisher.run(stop_event)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
