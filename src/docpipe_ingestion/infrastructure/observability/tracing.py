import atexit
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Event, Lock, Thread
from time import monotonic
from typing import Any, override

from opentelemetry import context, propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    TraceIdRatioBased,
)
from opentelemetry.trace import SpanKind
from opentelemetry.util.types import AttributeValue

from docpipe_ingestion.infrastructure.settings import Settings

logger = logging.getLogger(__name__)


class _BoundedTracerProvider(TracerProvider):
    """Drain on one daemon thread with a shared, bounded shutdown deadline.

    Start the thread during initialization: Python forbids starting threads
    from an atexit callback. Never wait for the SDK's unbounded force_flush.
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(
            sampler=_sampler(settings),
            resource=Resource.create({
                'service.name': settings.service_name,
                'deployment.environment.name': settings.environment,
            }),
            shutdown_on_exit=False,
        )
        self._shutdown_timeout = settings.telemetry_shutdown_timeout_seconds
        self._shutdown_lock = Lock()
        self._shutdown_requested = Event()
        self._shutdown_finished = Event()
        self._shutdown_deadline: float | None = None
        Thread(
            target=self._finish_shutdown,
            name='docpipe-telemetry-shutdown',
            daemon=True,
        ).start()
        atexit.register(self.shutdown)

    def _finish_shutdown(self) -> None:
        self._shutdown_requested.wait()
        try:
            # SDK shutdown already drains the batch processor's queue.
            super().shutdown()
        except Exception as error:
            logger.warning(
                'telemetry shutdown failed',
                extra={
                    'operation': 'telemetry.shutdown',
                    'error_category': type(error).__name__,
                },
            )
        finally:
            self._shutdown_finished.set()

    @override
    def shutdown(self) -> None:
        with self._shutdown_lock:
            first_call = self._shutdown_deadline is None
            if first_call:
                self._shutdown_deadline = monotonic() + self._shutdown_timeout
                atexit.unregister(self.shutdown)
                self._shutdown_requested.set()
            assert self._shutdown_deadline is not None
            remaining = max(0.0, self._shutdown_deadline - monotonic())
        if not self._shutdown_finished.wait(remaining) and first_call:
            logger.warning(
                'telemetry shutdown deadline exceeded; spans may be lost',
                extra={'operation': 'telemetry.shutdown', 'status': 'timeout'},
            )


def _sampler(settings: Settings) -> Any:
    if settings.traces_sampler == 'always_on':
        return ALWAYS_ON
    if settings.traces_sampler == 'always_off':
        return ALWAYS_OFF
    return ParentBased(TraceIdRatioBased(settings.traces_sample_ratio))


def create_tracer_provider(
    settings: Settings,
    *,
    exporter: SpanExporter | None = None,
) -> TracerProvider:
    provider = _BoundedTracerProvider(settings)
    selected = exporter
    if selected is None and settings.traces_enabled:
        selected = OTLPSpanExporter(
            endpoint=f'{str(settings.otlp_endpoint).rstrip("/")}/v1/traces',
            timeout=settings.otlp_timeout_seconds,
        )
    if selected is not None:
        provider.add_span_processor(BatchSpanProcessor(selected))
    return provider


def tracer(provider: TracerProvider | None = None) -> trace.Tracer:
    return trace.get_tracer('docpipe_ingestion', tracer_provider=provider)


@contextmanager
def span(
    name: str,
    *,
    provider: TracerProvider | None = None,
    attributes: dict[str, AttributeValue] | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
    carrier: dict[str, str] | None = None,
) -> Iterator[trace.Span]:
    parent = propagate.extract(carrier) if carrier else None
    with tracer(provider).start_as_current_span(
        name, context=parent, attributes=attributes, kind=kind
    ) as current:
        yield current


def current_trace_context() -> dict[str, str] | None:
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier or None


def attach_trace_context(carrier: dict[str, str] | None) -> object | None:
    if not carrier:
        return None
    return context.attach(propagate.extract(carrier))


def detach_trace_context(token: object | None) -> None:
    if token is not None:
        context.detach(token)  # type: ignore[arg-type]
