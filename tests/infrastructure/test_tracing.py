import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from threading import Event
from typing import cast
from unittest.mock import Mock

import pytest
import requests
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from pydantic import AnyHttpUrl

from docpipe_ingestion.infrastructure.observability import tracing
from docpipe_ingestion.infrastructure.settings import Settings


@pytest.mark.parametrize('failure', ['unavailable', 'timeout', 'connection'])
def test_otlp_transport_failures_return_with_finite_attempts(
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        'opentelemetry.exporter.otlp.proto.http.trace_exporter.time',
        lambda: 0.0,
    )
    session = Mock()
    session.post.return_value = Mock(
        ok=False, status_code=503, reason='Service unavailable'
    )
    if failure == 'timeout':
        session.post.side_effect = requests.exceptions.Timeout()
    if failure == 'connection':
        session.post.side_effect = requests.exceptions.ConnectionError()
    # Less than the minimum retry backoff: no real sleep or network involved.
    timeout = 0.01
    exporter = OTLPSpanExporter(
        endpoint='http://telemetry.invalid/v1/traces',
        timeout=timeout,
        session=session,
    )
    try:
        assert exporter.export([]) == SpanExportResult.FAILURE
    finally:
        cast(SpanExporter, exporter).shutdown()
    expected_attempts = 2 if failure == 'connection' else 1
    assert session.post.call_count == expected_attempts
    for call in session.post.call_args_list:
        assert 0 < call.kwargs['timeout'] <= timeout
    session.close.assert_called_once()


def test_disabled_export_does_not_create_otlp_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(side_effect=AssertionError('unexpected OTLP client'))
    monkeypatch.setattr(tracing, 'OTLPSpanExporter', client)
    provider = tracing.create_tracer_provider(Settings(traces_enabled=False))
    try:
        with tracing.span('local.operation', provider=provider):
            assert tracing.current_trace_context() is not None
    finally:
        provider.shutdown()
    client.assert_not_called()


def test_export_uses_configured_endpoint_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = InMemorySpanExporter()
    client = Mock(return_value=exporter)
    monkeypatch.setattr(tracing, 'OTLPSpanExporter', client)
    provider = tracing.create_tracer_provider(
        Settings(
            traces_enabled=True,
            traces_exporter='otlp',
            otlp_endpoint=AnyHttpUrl('http://telemetry.invalid/custom/'),
            otlp_timeout_seconds=0.5,
        )
    )
    with tracing.span('completed.operation', provider=provider):
        pass
    provider.shutdown()
    client.assert_called_once_with(
        endpoint='http://telemetry.invalid/custom/v1/traces', timeout=0.5
    )
    assert [item.name for item in exporter.get_finished_spans()] == [
        'completed.operation'
    ]


class BlockingExporter(SpanExporter):
    def __init__(self) -> None:
        self.entered = Event()
        self.release = Event()
        self.closed = Event()
        self.batches: list[list[str]] = []
        self.close_count = 0

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.batches.append([item.name for item in spans])
        self.entered.set()
        self.release.wait()
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self.close_count += 1
        self.closed.set()


def test_full_queue_drops_spans_and_shutdown_does_not_wait_for_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('OTEL_BSP_MAX_QUEUE_SIZE', '2')
    monkeypatch.setenv('OTEL_BSP_MAX_EXPORT_BATCH_SIZE', '1')
    exporter = BlockingExporter()
    provider = tracing.create_tracer_provider(
        Settings(telemetry_shutdown_timeout_seconds=0.01), exporter=exporter
    )
    try:
        with tracing.span('in.flight', provider=provider):
            pass
        assert exporter.entered.wait(5), 'batch export did not start'
        for name in ('dropped', 'retained.first', 'retained.second'):
            with tracing.span(name, provider=provider):
                pass
        # These calls must return while the exporter is still blocked.
        provider.shutdown()
        provider.shutdown()
        assert not exporter.closed.is_set()
    finally:
        exporter.release.set()
        assert exporter.closed.wait(5), 'exporter did not close'
        provider.shutdown()
    assert exporter.batches == [
        ['in.flight'],
        ['retained.first'],
        ['retained.second'],
    ]
    assert exporter.close_count == 1


def test_shutdown_error_is_reported_without_exporter_details(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = InMemorySpanExporter()
    shutdown = Mock(side_effect=RuntimeError('private-endpoint'))
    monkeypatch.setattr(exporter, 'shutdown', shutdown)
    provider = tracing.create_tracer_provider(Settings(), exporter=exporter)
    provider.shutdown()
    provider.shutdown()
    shutdown.assert_called_once()
    assert 'telemetry shutdown failed' in caplog.text
    assert 'private-endpoint' not in caplog.text


@pytest.mark.parametrize('explicit_shutdown', [False, True])
def test_process_exit_is_bounded_even_with_blocked_exporter_shutdown(
    explicit_shutdown: bool,
    tmp_path: Path,
) -> None:
    code = """
from threading import Event
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from docpipe_ingestion.infrastructure.observability.tracing import (
    create_tracer_provider,
)
from docpipe_ingestion.infrastructure.settings import Settings

class Blocked(SpanExporter):
    def shutdown(self):
        Event().wait()

provider = create_tracer_provider(Settings(
    _env_file=None, telemetry_shutdown_timeout_seconds=0.01,
))
provider.add_span_processor(SimpleSpanProcessor(Blocked()))
"""
    if explicit_shutdown:
        code += '\nprovider.shutdown()\nprovider.shutdown()\n'
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(('DOCPIPE_', 'OTEL_'))
    }
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=str(tmp_path),
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert 'telemetry shutdown deadline exceeded' in result.stderr
    assert 'Exception ignored in atexit callback' not in result.stderr
