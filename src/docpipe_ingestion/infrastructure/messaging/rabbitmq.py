"""RabbitMQ implementation of confirmed event publication."""

import json
from typing import Any

import pika  # type: ignore[import-untyped]
from pika.adapters.blocking_connection import (  # type: ignore[import-untyped]
    BlockingChannel,
)

from docpipe_ingestion.application.errors import BrokerPublishError
from docpipe_ingestion.domain.models import OutboxEvent


class RabbitMQPublisher:
    """Declare durable topology and wait for broker publisher confirms."""

    def __init__(
        self,
        *,
        url: str,
        exchange: str,
        queue: str,
        routing_key: str,
        timeout_seconds: float,
    ) -> None:
        self._exchange = exchange
        self._routing_key = routing_key
        try:
            self._connection, self._channel = self._connect(
                url,
                timeout_seconds,
                queue,
            )
        except Exception as error:
            raise BrokerPublishError(
                'RabbitMQ connection or topology setup failed'
            ) from error

    def _connect(
        self,
        url: str,
        timeout_seconds: float,
        queue: str,
    ) -> tuple[Any, BlockingChannel]:
        parameters = pika.URLParameters(url)
        parameters.socket_timeout = timeout_seconds
        parameters.stack_timeout = timeout_seconds
        parameters.blocked_connection_timeout = timeout_seconds
        connection = pika.BlockingConnection(parameters)
        channel: BlockingChannel = connection.channel()
        channel.exchange_declare(
            exchange=self._exchange,
            exchange_type='direct',
            durable=True,
        )
        channel.queue_declare(queue=queue, durable=True)
        channel.queue_bind(
            queue=queue,
            exchange=self._exchange,
            routing_key=self._routing_key,
        )
        channel.confirm_delivery()
        return connection, channel

    def publish(self, event: OutboxEvent) -> None:
        try:
            self._channel.basic_publish(
                exchange=self._exchange,
                routing_key=self._routing_key,
                body=json.dumps(
                    event.payload,
                    separators=(',', ':'),
                    sort_keys=True,
                ).encode(),
                mandatory=True,
                properties=pika.BasicProperties(
                    content_type='application/json',
                    content_encoding='utf-8',
                    delivery_mode=2,
                    message_id=str(event.id),
                    type=event.event_type,
                    correlation_id=str(event.payload['correlation_id']),
                ),
            )
        except BrokerPublishError:
            raise
        except Exception as error:
            raise BrokerPublishError(
                'RabbitMQ publication was not confirmed'
            ) from error

    def close(self) -> None:
        if self._connection.is_open:
            self._connection.close()
