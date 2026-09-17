from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import Request, status
from starlette.responses import Response

from docpipe_ingestion.api.exception_handlers import (
    CORRELATION_HEADER,
    error_response,
)

type RequestHandler = Callable[[Request], Awaitable[Response]]


async def correlate_request(
    request: Request,
    call_next: RequestHandler,
) -> Response:
    """Propagate a valid client correlation UUID or create a new one."""
    supplied_value = request.headers.get(CORRELATION_HEADER)
    try:
        correlation_id = UUID(supplied_value) if supplied_value else uuid4()
    except ValueError:
        request.state.correlation_id = uuid4()
        return error_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            code='invalid_correlation_id',
            message='X-Correlation-ID must be a valid UUID.',
        )
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers[CORRELATION_HEADER] = str(correlation_id)
    return response
