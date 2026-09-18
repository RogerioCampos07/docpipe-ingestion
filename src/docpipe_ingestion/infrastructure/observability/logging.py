import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace

from docpipe_ingestion.infrastructure.observability.context import (
    current_correlation_id,
)
from docpipe_ingestion.infrastructure.settings import Settings

_RESERVED = set(logging.makeLogRecord({}).__dict__) | {
    'message',
    'asctime',
}


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str, environment: str) -> None:
        super().__init__()
        self._service = service
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span().get_span_context()
        correlation_id = current_correlation_id()
        data: dict[str, Any] = {
            'timestamp': datetime.now(UTC).isoformat(),
            'level': record.levelname,
            'service': self._service,
            'environment': self._environment,
            'correlation_id': (
                str(correlation_id) if correlation_id is not None else None
            ),
            'trace_id': f'{span.trace_id:032x}' if span.is_valid else None,
            'span_id': f'{span.span_id:016x}' if span.is_valid else None,
            'message': record.getMessage(),
            'operation': getattr(record, 'operation', None),
            'status': getattr(record, 'status', None),
            'duration_ms': getattr(record, 'duration_ms', None),
            'dependency_type': getattr(record, 'dependency_type', None),
            'dependency_backend': getattr(record, 'dependency_backend', None),
            'error_category': getattr(record, 'error_category', None),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in data and key != 'exc_info':
                data[key] = value
        if record.exc_info is not None:
            error_type = record.exc_info[0]
            data['exception_type'] = (
                error_type.__name__ if error_type is not None else 'Exception'
            )
        return json.dumps(data, default=str, separators=(',', ':'))


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stderr)
    if settings.log_format == 'json':
        handler.setFormatter(
            JsonFormatter(settings.service_name, settings.environment)
        )
    else:
        handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)
    for name in (
        'uvicorn.access',
        'azure.core.pipeline.policies.http_logging_policy',
    ):
        logging.getLogger(name).disabled = True
    for name in ('azure', 'sqlalchemy.engine'):
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.getLogger('pika').setLevel(logging.CRITICAL)
