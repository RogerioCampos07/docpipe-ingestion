import json
import logging
from io import StringIO
from typing import cast
from uuid import UUID

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import Span
from prometheus_client import CollectorRegistry, generate_latest

from docpipe_ingestion.api.app import sanitize_server_span
from docpipe_ingestion.infrastructure.observability.context import correlated
from docpipe_ingestion.infrastructure.observability.logging import (
    JsonFormatter,
)
from docpipe_ingestion.infrastructure.observability.metrics import (
    create_metrics,
)
from docpipe_ingestion.infrastructure.observability.tracing import (
    create_tracer_provider,
    current_trace_context,
    span,
)
from docpipe_ingestion.infrastructure.settings import Settings

CORRELATION_ID = UUID('87654321-4321-8765-4321-876543218765')
TRACE_ID_LENGTH = 32


class RecordingSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}

    @staticmethod
    def is_recording() -> bool:
        return True

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


def test_json_log_contains_correlation_and_trace_without_sensitive_data() -> (
    None
):
    exporter = InMemorySpanExporter()
    provider = create_tracer_provider(Settings(environment='test'))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonFormatter('DocPipe Ingestion', 'test'))
    logger = logging.getLogger('test.observability')
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    with correlated(CORRELATION_ID), span('test.operation', provider=provider):
        logger.info(
            'operation completed',
            extra={'operation': 'test.operation', 'status': 'ok'},
        )

    data = json.loads(output.getvalue())
    assert data['correlation_id'] == str(CORRELATION_ID)
    assert len(data['trace_id']) == TRACE_ID_LENGTH
    assert data['operation'] == 'test.operation'
    assert 'private.pdf' not in output.getvalue()
    provider.shutdown()


def test_trace_context_is_w3c_and_spans_have_expected_parent() -> None:
    exporter = InMemorySpanExporter()
    provider = create_tracer_provider(Settings(environment='test'))
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    with span('parent', provider=provider):
        carrier = current_trace_context()
        with span('child', provider=provider):
            pass

    spans = {item.name: item for item in exporter.get_finished_spans()}
    assert carrier is not None
    assert set(carrier) <= {'traceparent', 'tracestate'}
    assert spans['child'].parent is not None
    assert spans['child'].parent.span_id == spans['parent'].context.span_id
    provider.shutdown()


def test_metric_registries_are_isolated_and_have_bounded_labels() -> None:
    first = create_metrics(CollectorRegistry())
    second = create_metrics(CollectorRegistry())
    first.http_requests.labels(
        'GET', '/v1/documents/{document_id}', '200'
    ).inc()

    first_text = generate_latest(first.registry).decode()
    second_text = generate_latest(second.registry).decode()
    assert 'route="/v1/documents/{document_id}"' in first_text
    assert 'document_id=' not in first_text
    assert 'correlation_id=' not in first_text
    assert 'method="GET"' not in second_text


def test_server_span_removes_request_identity_attributes() -> None:
    recording = RecordingSpan()

    sanitize_server_span(
        cast(Span, recording),
        {
            'path': '/v1/documents',
            'client': ('192.0.2.1', 1234),
            'headers': [(b'user-agent', b'private-agent')],
        },
    )

    assert recording.attributes == {
        'http.url': '/v1/documents',
        'http.user_agent': 'redacted',
        'net.peer.ip': 'redacted',
        'net.peer.port': 0,
        'http.host': 'redacted',
        'http.server_name': 'redacted',
    }
