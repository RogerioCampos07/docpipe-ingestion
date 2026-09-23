"""Independent command for the transactional outbox publisher."""

import logging
import signal
from functools import partial
from threading import Event

from sqlalchemy import text

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
from docpipe_ingestion.infrastructure.observability.logging import (
    configure_logging,
)
from docpipe_ingestion.infrastructure.observability.metrics import (
    create_metrics,
)
from docpipe_ingestion.infrastructure.observability.tracing import (
    create_tracer_provider,
)
from docpipe_ingestion.infrastructure.observability.worker_server import (
    WorkerMonitoringServer,
)
from docpipe_ingestion.infrastructure.settings import Settings


def main() -> None:
    settings = Settings()
    configure_logging(settings)
    logger = logging.getLogger(__name__)
    metrics = create_metrics()
    metrics.database_backend.labels(settings.database_backend).set(1)
    metrics.storage_backend.labels(settings.storage_backend).set(1)
    tracer_provider = create_tracer_provider(settings)
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
        tracer_provider=tracer_provider,
    )
    publisher = OutboxPublisher(
        unit_of_work_factory=partial(
            SqlAlchemyUnitOfWork,
            session_factory,
            metrics=metrics,
            backend=settings.database_backend,
            tracer_provider=tracer_provider,
        ),
        broker=broker,
        settings=PublisherSettings(
            batch_size=settings.outbox_batch_size,
            max_attempts=settings.outbox_max_attempts,
            backoff_seconds=settings.outbox_backoff_seconds,
            polling_seconds=settings.outbox_polling_seconds,
        ),
        metrics=metrics,
        tracer_provider=tracer_provider,
    )
    monitoring = None
    if settings.worker_monitoring_enabled:

        def worker_ready() -> bool:
            try:
                with engine.connect() as connection:
                    connection.execute(text('SELECT 1'))
                return broker.is_ready()
            except Exception:
                return False

        monitoring = WorkerMonitoringServer(
            settings.worker_metrics_host,
            settings.worker_metrics_port,
            metrics,
            worker_ready,
        )
        monitoring.start()
    logger.info(
        'outbox worker started',
        extra={'operation': 'service.start', 'status': 'started'},
    )
    try:
        publisher.run(stop_event)
    finally:
        if monitoring is not None:
            monitoring.close()
        engine.dispose()
        tracer_provider.shutdown()
        logger.info(
            'outbox worker stopped',
            extra={'operation': 'service.stop', 'status': 'stopped'},
        )


if __name__ == '__main__':
    main()
