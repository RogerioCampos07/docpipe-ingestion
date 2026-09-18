import logging
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import Request, status
from starlette.responses import Response

from docpipe_ingestion.api.exception_handlers import (
    CORRELATION_HEADER,
    error_response,
)
from docpipe_ingestion.infrastructure.observability.context import (
    reset_correlation_id,
    set_correlation_id,
)

type RequestHandler = Callable[[Request], Awaitable[Response]]
logger = logging.getLogger(__name__)


async def correlate_request(
    request: Request,
    call_next: RequestHandler,
) -> Response:
    """Propagate a valid client correlation UUID or create a new one."""
    supplied_value = request.headers.get(CORRELATION_HEADER)
    try:
        correlation_id = UUID(supplied_value) if supplied_value else uuid4()
    except ValueError:
        correlation_id = uuid4()
        request.state.correlation_id = correlation_id
        token = set_correlation_id(correlation_id)
        try:
            request.app.state.metrics.validation_failures.labels(
                'invalid_correlation_id'
            ).inc()
            request.app.state.metrics.http_requests.labels(
                request.method, 'unmatched', '400'
            ).inc()
            logger.info(
                'invalid correlation identifier',
                extra={
                    'operation': 'http.request',
                    'status': 400,
                    'error_category': 'invalid_correlation_id',
                },
            )
            return error_response(
                request,
                status_code=status.HTTP_400_BAD_REQUEST,
                code='invalid_correlation_id',
                message='X-Correlation-ID must be a valid UUID.',
            )
        finally:
            reset_correlation_id(token)
    request.state.correlation_id = correlation_id
    token = set_correlation_id(correlation_id)
    try:
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = str(correlation_id)
        return response
    finally:
        reset_correlation_id(token)
