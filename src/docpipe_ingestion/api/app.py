from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import Span

from docpipe_ingestion.api.correlation import correlate_request
from docpipe_ingestion.api.dependencies import (
    ApplicationServiceProvider,
    ApplicationServices,
)
from docpipe_ingestion.api.exception_handlers import install_exception_handlers
from docpipe_ingestion.api.routes.documents import router as documents_router
from docpipe_ingestion.api.routes.health import router as health_router
from docpipe_ingestion.api.routes.metrics import router as metrics_router
from docpipe_ingestion.infrastructure.observability.http import (
    create_http_observer,
)
from docpipe_ingestion.infrastructure.observability.logging import (
    configure_logging,
)
from docpipe_ingestion.infrastructure.observability.metrics import (
    create_metrics,
)
from docpipe_ingestion.infrastructure.observability.tracing import (
    create_tracer_provider,
    shutdown_tracer_provider,
)
from docpipe_ingestion.infrastructure.settings import Settings, get_settings


def sanitize_server_span(span: Span, scope: dict[str, Any]) -> None:
    if not span.is_recording():
        return
    path = scope.get('path', '')
    span.set_attribute('http.url', str(path))
    span.set_attribute('http.user_agent', 'redacted')
    span.set_attribute('net.peer.ip', 'redacted')
    span.set_attribute('net.peer.port', 0)
    span.set_attribute('http.host', 'redacted')
    span.set_attribute('http.server_name', 'redacted')


def create_app(
    settings: Settings | None = None,
    *,
    services: ApplicationServices | None = None,
) -> FastAPI:
    """Create and configure the HTTP application."""
    current_settings = settings or get_settings()
    configure_logging(current_settings)
    metrics = create_metrics()
    tracer_provider = create_tracer_provider(current_settings)
    service_provider = ApplicationServiceProvider(
        current_settings,
        services,
        metrics=metrics,
        tracer_provider=tracer_provider,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        del application
        try:
            yield
        finally:
            service_provider.close()
            shutdown_tracer_provider(
                tracer_provider,
                current_settings.telemetry_shutdown_timeout_seconds,
            )

    application = FastAPI(
        title=current_settings.service_name,
        version='1.0.0',
        description='Private document ingestion API for DocPipe.',
        lifespan=lifespan,
    )
    application.state.settings = current_settings
    application.state.service_provider = service_provider
    application.state.metrics = metrics
    application.state.tracer_provider = tracer_provider
    metrics.database_backend.labels(current_settings.database_backend).set(1)
    metrics.storage_backend.labels(current_settings.storage_backend).set(1)
    application.middleware('http')(create_http_observer(metrics))
    application.middleware('http')(correlate_request)
    install_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(metrics_router)
    application.include_router(documents_router)
    if current_settings.traces_enabled:
        FastAPIInstrumentor.instrument_app(
            application,
            tracer_provider=tracer_provider,
            excluded_urls='health/live,health/ready,metrics',
            server_request_hook=sanitize_server_span,
            exclude_spans=['receive', 'send'],
        )

    def custom_openapi() -> dict[str, Any]:
        if application.openapi_schema is None:
            schema = get_openapi(
                title=application.title,
                version=application.version,
                description=application.description,
                routes=application.routes,
            )
            for path in schema.get('paths', {}).values():
                for operation in path.values():
                    if isinstance(operation, dict):
                        operation.get('responses', {}).pop('422', None)
            application.openapi_schema = schema
        return application.openapi_schema

    application.openapi = custom_openapi  # type: ignore[method-assign]
    return application


app = create_app()
