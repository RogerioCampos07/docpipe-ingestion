from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

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
    provider = TracerProvider(
        sampler=_sampler(settings),
        resource=Resource.create({
            'service.name': settings.service_name,
            'deployment.environment.name': settings.environment,
        }),
    )
    selected = exporter
    if selected is None and settings.traces_enabled:
        selected = OTLPSpanExporter(
            endpoint=f'{str(settings.otlp_endpoint).rstrip("/")}/v1/traces',
            timeout=settings.otlp_timeout_seconds,
        )
    if selected is not None:
        provider.add_span_processor(BatchSpanProcessor(selected))
    return provider


def shutdown_tracer_provider(
    provider: TracerProvider,
    timeout_seconds: float,
) -> None:
    """Flush completed spans within a bound, then close processors."""
    provider.force_flush(timeout_millis=int(timeout_seconds * 1000))
    provider.shutdown()


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
