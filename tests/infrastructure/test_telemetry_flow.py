import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from sqlalchemy import Engine, select

from docpipe_ingestion.api.app import create_app
from docpipe_ingestion.application.publish_outbox import (
    OutboxPublisher,
    PublisherSettings,
)
from docpipe_ingestion.infrastructure.database.engine import (
    SessionFactory,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.models import OutboxEventModel
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from docpipe_ingestion.infrastructure.messaging.rabbitmq import (
    RabbitMQPublisher,
)
from docpipe_ingestion.infrastructure.observability import tracing
from docpipe_ingestion.infrastructure.observability.logging import (
    configure_logging,
)
from docpipe_ingestion.infrastructure.observability.metrics import (
    create_metrics,
)
from docpipe_ingestion.infrastructure.settings import Settings

CORRELATION_ID = '87654321-4321-8765-4321-876543218765'
TRACE_ID = '1234567890abcdef1234567890abcdef'
TRACEPARENT = f'00-{TRACE_ID}-1234567890abcdef-01'


class FailingExporter(InMemorySpanExporter):
    def __init__(self, raises: bool) -> None:
        super().__init__()
        self.raises = raises

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        super().export(spans)
        if self.raises:
            raise RuntimeError('simulated exporter failure')
        return SpanExportResult.FAILURE


@dataclass
class TelemetryFlow:
    application: FastAPI
    factory: SessionFactory
    worker_provider: TracerProvider
    api_exporter: InMemorySpanExporter
    worker_exporter: InMemorySpanExporter
    broker: RabbitMQPublisher
    channel: Mock
    otlp: Mock
    enabled: bool


def _exporter(mode: str) -> InMemorySpanExporter:
    if mode in {'failure', 'exception'}:
        return FailingExporter(mode == 'exception')
    return InMemorySpanExporter()


@pytest.fixture(params=['disabled', 'success', 'failure', 'exception'])
def flow(
    request: pytest.FixtureRequest,
    database_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> Iterator[TelemetryFlow]:
    enabled = request.param != 'disabled'
    api_exporter = _exporter(request.param)
    otlp = Mock(return_value=api_exporter)
    monkeypatch.setattr(tracing, 'OTLPSpanExporter', otlp)
    settings = Settings(
        database_url=str(database_engine.url),
        storage_root=tmp_path / 'documents',
        traces_enabled=enabled,
        traces_exporter='otlp' if enabled else 'none',
    )
    settings.storage_root.mkdir()
    application = create_app(settings)
    factory = create_session_factory(database_engine)
    channel = Mock(is_open=True)
    monkeypatch.setattr(
        RabbitMQPublisher,
        '_connect',
        lambda *args: (Mock(is_open=True), channel),
    )
    worker_exporter = _exporter(request.param)
    worker_provider = tracing.create_tracer_provider(
        Settings(), exporter=worker_exporter
    )
    broker = RabbitMQPublisher(
        url='amqp://unused',
        exchange='events',
        queue='documents',
        routing_key='document.received.v1',
        timeout_seconds=1,
        tracer_provider=worker_provider,
    )
    try:
        yield TelemetryFlow(
            application,
            factory,
            worker_provider,
            api_exporter,
            worker_exporter,
            broker,
            channel,
            otlp,
            enabled,
        )
    finally:
        application.state.tracer_provider.shutdown()
        broker.close()
        worker_provider.shutdown()


@pytest.mark.parametrize('legacy_event', [False, True])
def test_ingestion_publication_and_signals_survive_export_failure(
    flow: TelemetryFlow,
    capsys: pytest.CaptureFixture[str],
    legacy_event: bool,
) -> None:
    configure_logging(flow.application.state.settings)
    metrics = create_metrics()
    with TestClient(flow.application) as client:
        response = client.post(
            '/v1/documents',
            files={
                'file': (
                    'private.pdf',
                    b'%PDF-1.7\nprivate-content',
                    'application/pdf',
                )
            },
            headers={
                'X-Correlation-ID': CORRELATION_ID,
                'traceparent': TRACEPARENT,
                'tracestate': 'vendor=value',
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()['correlation_id'] == CORRELATION_ID
        # Exercise exporter errors before continuing functional work.
        flow.application.state.tracer_provider.force_flush()
        if legacy_event:
            with flow.factory.begin() as session:
                session.scalars(
                    select(OutboxEventModel)
                ).one().trace_context = None
        assert client.get('/health/live').status_code == status.HTTP_200_OK
        assert client.get('/health/ready').status_code == status.HTTP_200_OK
        document_id = UUID(response.json()['document_id'])
        publisher = OutboxPublisher(
            unit_of_work_factory=partial(
                SqlAlchemyUnitOfWork,
                flow.factory,
                metrics=metrics,
                tracer_provider=flow.worker_provider,
            ),
            broker=flow.broker,
            settings=PublisherSettings(1, 3, 1, 1),
            metrics=metrics,
            tracer_provider=flow.worker_provider,
        )
        assert publisher.process_batch() == 1
        flow.worker_provider.force_flush()
        queried = client.get(f'/v1/documents/{document_id}')
        assert queried.json()['status'] == 'PUBLISHED'
        observed = client.get('/metrics')
        assert observed.status_code == status.HTTP_200_OK
        assert 'docpipe_ingestion_documents_accepted_total 1.0' in (
            observed.text
        )
        assert CORRELATION_ID not in observed.text
        assert str(document_id) not in observed.text
    _assert_delivery(flow, legacy_event)
    logs = capsys.readouterr().err
    assert CORRELATION_ID in logs
    assert 'private.pdf' not in logs
    assert 'private-content' not in logs


def _assert_delivery(flow: TelemetryFlow, legacy_event: bool) -> None:
    with flow.factory() as session:
        event = session.scalars(select(OutboxEventModel)).one()
        assert event.published_at is not None
        assert event.attempts == 1
        assert event.last_error is None
        assert 'traceparent' not in event.payload
        assert 'tracestate' not in event.payload
    sent = flow.channel.basic_publish.call_args.kwargs
    properties = sent['properties']
    assert properties.correlation_id == CORRELATION_ID
    assert json.loads(sent['body']) == event.payload
    worker_spans = flow.worker_exporter.get_finished_spans()
    assert {
        'outbox.publish_attempt',
        'rabbitmq.publish',
        'database.commit',
    } <= {item.name for item in worker_spans}
    if flow.enabled and not legacy_event:
        assert event.trace_context is not None
        assert event.trace_context['traceparent'].split('-')[1] == TRACE_ID
        assert properties.headers['traceparent'].split('-')[1] == TRACE_ID
        assert properties.headers['tracestate'] == 'vendor=value'
        attempt = next(
            item
            for item in worker_spans
            if item.name == 'outbox.publish_attempt'
        )
        published = next(
            item for item in worker_spans if item.name == 'rabbitmq.publish'
        )
        assert attempt.context is not None
        assert attempt.context.trace_id == int(TRACE_ID, 16)
        assert attempt.parent is not None
        assert attempt.parent.span_id == int(
            event.trace_context['traceparent'].split('-')[2], 16
        )
        assert published.parent is not None
        assert published.parent.span_id == attempt.context.span_id
        assert any(
            item.kind.name == 'SERVER'
            for item in flow.api_exporter.get_finished_spans()
        )
        assert all(item.context is not None for item in worker_spans)
    if legacy_event:
        assert event.trace_context is None
        attempt = next(
            item
            for item in worker_spans
            if item.name == 'outbox.publish_attempt'
        )
        assert attempt.parent is None
        assert properties.headers['traceparent'].split('-')[1] != TRACE_ID
    if not flow.enabled:
        flow.otlp.assert_not_called()
