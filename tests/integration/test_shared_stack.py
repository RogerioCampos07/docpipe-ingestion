import os
from functools import partial
from uuid import UUID, uuid4

import pika  # type: ignore[import-untyped]
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete

from docpipe_ingestion.api.app import create_app
from docpipe_ingestion.application.publish_outbox import (
    OutboxPublisher,
    PublisherSettings,
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
from docpipe_ingestion.infrastructure.messaging.rabbitmq import (
    RabbitMQPublisher,
)
from docpipe_ingestion.infrastructure.settings import Settings
from tests.integration.conftest import migrate

pytestmark = [
    pytest.mark.stack,
    pytest.mark.skipif(
        os.environ.get('DOCPIPE_STACK_INTEGRATION') != '1',
        reason='set DOCPIPE_STACK_INTEGRATION=1',
    ),
]


def test_postgresql_azurite_rabbitmq_flow(
    postgresql_url: str,
    azurite_connection_string: str,
) -> None:
    migrate(postgresql_url)
    container = f'stack-{uuid4().hex}'
    settings = Settings(
        environment='test',
        database_backend='postgresql',
        database_url=postgresql_url,
        storage_backend='azurite',
        blob_connection_string=SecretStr(azurite_connection_string),
        blob_container=container,
        blob_api_version='2023-11-03',
        storage_chunk_size_bytes=8,
    )
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    with factory.begin() as session:
        session.execute(delete(OutboxEventModel))
        session.execute(delete(DocumentModel))
    rabbit_connection = pika.BlockingConnection(
        pika.URLParameters(settings.rabbitmq_url)
    )
    rabbit_connection.channel().queue_purge(settings.rabbitmq_queue)
    rabbit_connection.close()
    content = b'%PDF-1.7\nshared stack document'
    try:
        with TestClient(create_app(settings)) as client:
            response = client.post(
                '/v1/documents',
                files={'file': ('shared.pdf', content, 'application/pdf')},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            document_id = UUID(response.json()['document_id'])
            broker = RabbitMQPublisher(
                url=settings.rabbitmq_url,
                exchange=settings.rabbitmq_exchange,
                queue=settings.rabbitmq_queue,
                routing_key=settings.rabbitmq_routing_key,
                timeout_seconds=settings.rabbitmq_timeout_seconds,
            )
            publisher = OutboxPublisher(
                unit_of_work_factory=partial(SqlAlchemyUnitOfWork, factory),
                broker=broker,
                settings=PublisherSettings(
                    batch_size=10,
                    max_attempts=5,
                    backoff_seconds=0.01,
                    polling_seconds=0.01,
                ),
            )
            assert publisher.process_batch() == 1
            broker.close()
            queried = client.get(f'/v1/documents/{document_id}')
            assert queried.status_code == status.HTTP_200_OK
            assert queried.json()['status'] == 'PUBLISHED'
            assert 'storage_key' not in queried.json()
    finally:
        engine.dispose()
