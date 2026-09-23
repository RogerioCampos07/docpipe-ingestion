import signal
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler
from io import BytesIO
from threading import Event
from unittest.mock import Mock

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from docpipe_ingestion import outbox_worker
from docpipe_ingestion.application.errors import BrokerPublishError
from docpipe_ingestion.infrastructure.observability import (
    tracing,
    worker_server,
)
from docpipe_ingestion.infrastructure.observability.metrics import (
    create_metrics,
)
from docpipe_ingestion.infrastructure.settings import Settings


@pytest.mark.parametrize(
    ('path', 'ready', 'expected'),
    [
        ('/metrics', False, b'docpipe_ingestion_documents_accepted_total 1.0'),
        ('/health/live', False, b'200 OK'),
        ('/health/ready', True, b'200 OK'),
        ('/health/ready', False, b'503 Service Unavailable'),
        ('/unknown', True, b'404 Not Found'),
    ],
)
def test_worker_endpoints_without_network_or_telemetry_backend(
    path: str,
    ready: bool,
    expected: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handlers: list[type[BaseHTTPRequestHandler]] = []
    server = Mock()

    def bind(
        address: tuple[str, int], handler: type[BaseHTTPRequestHandler]
    ) -> Mock:
        assert address == ('127.0.0.1', 9001)
        handlers.append(handler)
        return server

    monkeypatch.setattr(worker_server, 'ThreadingHTTPServer', bind)
    metrics = create_metrics()
    metrics.documents_accepted.inc()
    monitoring = worker_server.WorkerMonitoringServer(
        '127.0.0.1', 9001, metrics, lambda: ready
    )
    request = Mock()
    request.makefile.return_value = BytesIO(
        f'GET {path} HTTP/1.0\r\nHost: localhost\r\n\r\n'.encode()
    )
    monitoring.start()
    try:
        handlers[0](request, ('127.0.0.1', 12345), server)
        response = b''.join(
            call.args[0] for call in request.sendall.call_args_list
        )
        assert expected in response
    finally:
        monitoring.close()
    server.shutdown.assert_called_once()
    server.server_close.assert_called_once()


@pytest.mark.parametrize('dependency_failure', [None, 'database', 'broker'])
def test_worker_lifecycle_preserves_functional_readiness(
    dependency_failure: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    engine = Mock()
    engine.connect.return_value = Mock(
        __enter__=Mock(), __exit__=Mock(return_value=False)
    )
    if dependency_failure == 'database':
        engine.connect.side_effect = RuntimeError('database unavailable')
    broker = Mock()
    broker.is_ready.return_value = dependency_failure != 'broker'
    provider = tracing.create_tracer_provider(
        settings, exporter=InMemorySpanExporter()
    )
    monitoring = Mock()
    ready_checks: list[Callable[[], bool]] = []

    def monitor(*args: object) -> Mock:
        ready_checks.append(args[-1])  # type: ignore[arg-type]
        return monitoring

    def run(stop: Event) -> None:
        assert ready_checks[0]() is (dependency_failure is None)
        stop.set()

    monkeypatch.setattr(outbox_worker, 'Settings', lambda: settings)
    monkeypatch.setattr(
        outbox_worker, 'create_database_engine', Mock(return_value=engine)
    )
    monkeypatch.setattr(outbox_worker, 'create_session_factory', Mock())
    monkeypatch.setattr(
        outbox_worker, 'RabbitMQPublisher', Mock(return_value=broker)
    )
    monkeypatch.setattr(
        outbox_worker, 'OutboxPublisher', Mock(return_value=Mock(run=run))
    )
    monkeypatch.setattr(outbox_worker, 'WorkerMonitoringServer', monitor)
    monkeypatch.setattr(
        outbox_worker, 'create_tracer_provider', Mock(return_value=provider)
    )
    monkeypatch.setattr(signal, 'signal', Mock())
    try:
        outbox_worker.main()
    finally:
        provider.shutdown()
    monitoring.start.assert_called_once()
    monitoring.close.assert_called_once()
    engine.dispose.assert_called_once()


def test_worker_does_not_hide_broker_startup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = tracing.create_tracer_provider(Settings())
    monkeypatch.setattr(
        outbox_worker, 'create_tracer_provider', Mock(return_value=provider)
    )
    monkeypatch.setattr(outbox_worker, 'create_database_engine', Mock())
    monkeypatch.setattr(outbox_worker, 'create_session_factory', Mock())
    monkeypatch.setattr(signal, 'signal', Mock())
    monkeypatch.setattr(
        outbox_worker,
        'RabbitMQPublisher',
        Mock(side_effect=BrokerPublishError('broker unavailable')),
    )
    try:
        with pytest.raises(BrokerPublishError, match='broker unavailable'):
            outbox_worker.main()
    finally:
        provider.shutdown()
