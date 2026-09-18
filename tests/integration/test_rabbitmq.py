import os
from datetime import UTC, datetime
from uuid import UUID

import pika  # type: ignore[import-untyped]
import pytest

from docpipe_ingestion.domain.models import OutboxEvent
from docpipe_ingestion.infrastructure.messaging.rabbitmq import (
    RabbitMQPublisher,
)


@pytest.mark.rabbitmq
@pytest.mark.skipif(
    os.environ.get('DOCPIPE_RABBITMQ_INTEGRATION') != '1',
    reason='set DOCPIPE_RABBITMQ_INTEGRATION=1 for broker integration',
)
def test_rabbitmq_confirms_and_routes_document_event() -> None:
    url = os.environ.get(
        'DOCPIPE_INGESTION_RABBITMQ_URL',
        'amqp://docpipe:docpipe@localhost:5672/docpipe',
    )
    event_id = UUID('11111111-2222-3333-4444-555555555555')
    document_id = UUID('12345678-1234-5678-1234-567812345678')
    event = OutboxEvent(
        id=event_id,
        aggregate_id=document_id,
        event_type='document.received.v1',
        payload={
            'event_id': str(event_id),
            'event_type': 'document.received',
            'event_version': 1,
            'occurred_at': '2026-09-17T12:00:00Z',
            'correlation_id': '87654321-4321-8765-4321-876543218765',
            'document_id': str(document_id),
            'data': {
                'storage_key': f'{"a" * 32}.blob',
                'media_type': 'application/pdf',
                'size_bytes': 10,
                'sha256': 'b' * 64,
            },
        },
        created_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
    )
    publisher = RabbitMQPublisher(
        url=url,
        exchange='docpipe.events',
        queue='docpipe.document.received.v1',
        routing_key='document.received.v1',
        timeout_seconds=5,
    )
    connection = pika.BlockingConnection(pika.URLParameters(url))
    channel = connection.channel()
    channel.queue_purge('docpipe.document.received.v1')

    try:
        publisher.publish(event)
        method, properties, body = channel.basic_get(
            'docpipe.document.received.v1',
            auto_ack=True,
        )
    finally:
        publisher.close()
        connection.close()

    assert method is not None
    assert properties.message_id == str(event_id)
    assert b'"event_type":"document.received"' in body
