from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from docpipe_ingestion.api.correlation import correlate_request
from docpipe_ingestion.api.dependencies import (
    ApplicationServiceProvider,
    ApplicationServices,
)
from docpipe_ingestion.api.exception_handlers import install_exception_handlers
from docpipe_ingestion.api.routes.documents import router as documents_router
from docpipe_ingestion.api.routes.health import router as health_router
from docpipe_ingestion.infrastructure.settings import Settings, get_settings


def create_app(
    settings: Settings | None = None,
    *,
    services: ApplicationServices | None = None,
) -> FastAPI:
    """Create and configure the HTTP application."""
    current_settings = settings or get_settings()
    service_provider = ApplicationServiceProvider(current_settings, services)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        del application
        try:
            yield
        finally:
            service_provider.close()

    application = FastAPI(
        title=current_settings.service_name,
        version='1.0.0',
        description='Private document ingestion API for DocPipe.',
        lifespan=lifespan,
    )
    application.state.settings = current_settings
    application.state.service_provider = service_provider
    application.middleware('http')(correlate_request)
    install_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(documents_router)

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
