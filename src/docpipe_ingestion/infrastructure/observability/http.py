import logging
from time import perf_counter

from fastapi import Request
from starlette.responses import Response

from docpipe_ingestion.infrastructure.observability.metrics import Metrics

logger = logging.getLogger(__name__)
_EXCLUDED = {'/metrics', '/health/live', '/health/ready'}
_CLIENT_ERROR = 400


def normalized_route(request: Request) -> str:
    route = request.scope.get('route')
    path = getattr(route, 'path', None)
    return path if isinstance(path, str) else 'unmatched'


def create_http_observer(metrics: Metrics):  # type: ignore[no-untyped-def]
    async def observe(request: Request, call_next):  # type: ignore[no-untyped-def]
        started = perf_counter()
        received = 0
        original_receive = request.receive

        async def receive():  # type: ignore[no-untyped-def]
            nonlocal received
            message = await original_receive()
            if message['type'] == 'http.request':
                received += len(message.get('body', b''))
            return message

        request._receive = receive
        response: Response
        try:
            response = await call_next(request)
        except Exception:
            route = normalized_route(request)
            metrics.http_errors.labels(route, 'internal').inc()
            raise
        route = normalized_route(request)
        duration = perf_counter() - started
        if request.url.path not in _EXCLUDED:
            method = (
                request.method
                if request.method
                in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'}
                else 'OTHER'
            )
            code = str(response.status_code)
            metrics.http_requests.labels(method, route, code).inc()
            metrics.http_duration.labels(method, route, code).observe(duration)
            metrics.request_body_bytes.labels(route).inc(received)
            if response.status_code >= _CLIENT_ERROR:
                metrics.http_errors.labels(route, f'http_{code}').inc()
        if request.url.path != '/metrics':
            logger.info(
                'http request completed',
                extra={
                    'operation': 'http.request',
                    'status': response.status_code,
                    'duration_ms': round(duration * 1000, 3),
                    'http_method': request.method,
                    'http_route': route,
                },
            )
        return response

    return observe
