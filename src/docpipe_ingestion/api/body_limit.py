from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, status
from fastapi.responses import Response
from fastapi.routing import APIRoute
from python_multipart.multipart import parse_options_header
from starlette.exceptions import HTTPException
from starlette.types import Message

from docpipe_ingestion.api.exception_handlers import error_response

MULTIPART_OVERHEAD_BYTES = 64 * 1024


def _declares_oversized_body(request: Request, limit: int) -> bool:
    declared_size = request.headers.get('content-length')
    if declared_size is None:
        return False
    try:
        return int(declared_size) > limit
    except ValueError:
        return False


class _BodyTooLarge(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_413_CONTENT_TOO_LARGE)


class DocumentBodyLimitRoute(APIRoute):
    """Bound the upload body while FastAPI parses its multipart form."""

    def get_route_handler(
        self,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        route_handler = super().get_route_handler()

        async def limited_route(request: Request) -> Response:
            if request.method != 'POST':
                return await route_handler(request)

            limit = (
                request.app.state.settings.max_file_size_bytes
                + MULTIPART_OVERHEAD_BYTES
            )
            received = 0
            original_receive = request.receive
            content_type, parameters = parse_options_header(
                request.headers.get('content-type', '')
            )
            boundary = parameters.get(b'boundary')
            closing_boundary = (
                b'\r\n--' + boundary + b'--'
                if content_type == b'multipart/form-data' and boundary
                else None
            )
            tail = b''
            closed = False

            async def limited_receive() -> Message:
                nonlocal received, tail, closed
                message = await original_receive()
                if message['type'] == 'http.request':
                    chunk = message.get('body', b'')
                    received += len(chunk)
                    if received > limit:
                        raise _BodyTooLarge()
                    if closing_boundary is not None:
                        overlap = len(closing_boundary) - 1
                        closed = closed or (
                            closing_boundary in chunk
                            or closing_boundary in tail + chunk[:overlap]
                        )
                        tail = (tail + chunk[-overlap:])[-overlap:]
                        if not message.get('more_body', False) and not closed:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                return message

            try:
                if _declares_oversized_body(request, limit):
                    raise _BodyTooLarge()
                bounded_request = Request(
                    request.scope, receive=limited_receive
                )
                return await route_handler(bounded_request)
            except _BodyTooLarge:
                metrics: Any = request.app.state.metrics
                metrics.validation_failures.labels('too_large').inc()
                metrics.uploads.labels('rejected').inc()
                return error_response(
                    request,
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    code='file_too_large',
                    message='The upload exceeds the configured size limit.',
                )

        return limited_route
