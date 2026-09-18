from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from docpipe_ingestion.api.exception_handlers import error_response
from docpipe_ingestion.infrastructure.health import ReadinessChecker

router = APIRouter(tags=['health'])


class LivenessResponse(BaseModel):
    """Response returned when the process is alive."""

    status: Literal['ok'] = 'ok'


@router.get('/health/live', response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    """Report process liveness without checking external dependencies."""
    return LivenessResponse()


@router.get('/health/ready', response_model=None)
def readiness(request: Request) -> Response:
    """Report whether database and storage can accept an ingestion."""
    checks = ReadinessChecker(request.app.state.settings).check()
    metrics = request.app.state.metrics
    metrics.readiness.labels(
        'database', request.app.state.settings.database_backend
    ).set(int(checks['database']))
    metrics.readiness.labels(
        'storage', request.app.state.settings.storage_backend
    ).set(int(checks['storage']))
    if all(checks.values()):
        return JSONResponse({'status': 'ok'})
    return error_response(
        request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code='service_not_ready',
        message='The service is not ready to accept documents.',
    )
