from fastapi import FastAPI

from docpipe_ingestion.api.routes.health import router as health_router
from docpipe_ingestion.infrastructure.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the HTTP application."""
    current_settings = settings or get_settings()
    application = FastAPI(title=current_settings.service_name)
    application.state.settings = current_settings
    application.include_router(health_router)
    return application


app = create_app()
