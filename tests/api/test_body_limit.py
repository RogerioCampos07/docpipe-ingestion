import asyncio
import json
from tempfile import SpooledTemporaryFile
from typing import Any
from uuid import UUID

import pytest
import starlette.formparsers
from fastapi.testclient import TestClient
from prometheus_client import generate_latest
from starlette.datastructures import UploadFile
from starlette.status import (
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_413_CONTENT_TOO_LARGE,
)
from starlette.types import Message

from docpipe_ingestion.api.app import create_app
from docpipe_ingestion.api.body_limit import MULTIPART_OVERHEAD_BYTES
from docpipe_ingestion.api.dependencies import ApplicationServices
from docpipe_ingestion.infrastructure.settings import Settings
from tests.api.test_documents import (
    StubGetDocument,
    StubIngestDocument,
    _document,
)

BOUNDARY = b'docpipe-boundary'
CORRELATION_ID = UUID('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')


def _multipart(content: bytes, *, ending: bytes | None = None) -> bytes:
    beginning = (
        b'--' + BOUNDARY + b'\r\n'
        b'Content-Disposition: form-data; name="file"; filename="sample.pdf"'
        b'\r\nContent-Type: application/pdf\r\n\r\n'
    )
    if ending is None:
        ending = b'\r\n--' + BOUNDARY + b'--\r\n'
    return beginning + content + ending


def _app(max_file_size_bytes: int = 8) -> tuple[Any, StubIngestDocument]:
    ingest = StubIngestDocument(result=_document())
    app = create_app(
        Settings(environment='test', max_file_size_bytes=max_file_size_bytes),
        services=ApplicationServices(
            ingest_document=ingest,
            get_document=StubGetDocument(result=_document()),
        ),
    )
    return app, ingest


def _asgi_request(
    app: Any,
    chunks: list[bytes],
    *,
    content_length: str | None = None,
    disconnect: bool = False,
) -> tuple[int, dict[str, str], bytes, int]:
    headers = [
        (b'content-type', b'multipart/form-data; boundary=' + BOUNDARY),
        (b'x-correlation-id', str(CORRELATION_ID).encode()),
    ]
    if content_length is not None:
        headers.append((b'content-length', content_length.encode()))
    scope = {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'http_version': '1.1',
        'method': 'POST',
        'scheme': 'http',
        'path': '/v1/documents',
        'raw_path': b'/v1/documents',
        'root_path': '',
        'query_string': b'',
        'headers': headers,
        'client': ('testclient', 1234),
        'server': ('testserver', 80),
    }
    messages: list[Message] = [
        {'type': 'http.request', 'body': chunk, 'more_body': True}
        for chunk in chunks[:-1]
    ]
    if disconnect:
        messages.append({'type': 'http.disconnect'})
    else:
        messages.append({
            'type': 'http.request',
            'body': chunks[-1],
            'more_body': False,
        })
    sent: list[Message] = []
    delivered = 0

    async def receive() -> Message:
        nonlocal delivered
        if delivered < len(messages):
            message = messages[delivered]
            delivered += 1
            return message
        await asyncio.sleep(0)
        return {'type': 'http.disconnect'}

    async def send(message: Message) -> None:
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    starts = [m for m in sent if m['type'] == 'http.response.start']
    assert len(starts) == 1
    response_headers = {
        name.decode().lower(): value.decode()
        for name, value in starts[0]['headers']
    }
    body = b''.join(
        m.get('body', b'') for m in sent if m['type'] == 'http.response.body'
    )
    return starts[0]['status'], response_headers, body, delivered


def _assert_too_large(
    status: int, headers: dict[str, str], body: bytes
) -> None:
    payload = json.loads(body)
    assert status == HTTP_413_CONTENT_TOO_LARGE
    assert payload['error']['code'] == 'file_too_large'
    assert headers['content-type'] == 'application/json'
    assert headers['x-correlation-id'] == str(CORRELATION_ID)
    assert payload['error']['correlation_id'] == str(CORRELATION_ID)


def test_valid_upload_and_exact_file_limit() -> None:
    app, ingest = _app()
    with TestClient(app) as client:
        response = client.post(
            '/v1/documents',
            files={'file': ('sample.pdf', b'%PDF-123', 'application/pdf')},
        )
    assert response.status_code == HTTP_202_ACCEPTED
    assert ingest.received_content == b'%PDF-123'


def test_exact_total_limit_accepts_valid_multipart() -> None:
    app, ingest = _app()
    body = _multipart(b'%PDF-123')
    limit = 8 + MULTIPART_OVERHEAD_BYTES
    body += b' ' * (
        limit - len(body)
    )  # MIME epilogue after the closing boundary.
    status, _, _, _ = _asgi_request(app, [body], content_length=str(limit))
    assert len(body) == limit
    assert status == HTTP_202_ACCEPTED
    assert ingest.received_content == b'%PDF-123'


def test_valid_chunked_upload_without_content_length() -> None:
    app, ingest = _app()
    body = _multipart(b'%PDF-123')
    status, _, _, _ = _asgi_request(app, [body[:37], body[37:]])
    assert status == HTTP_202_ACCEPTED
    assert ingest.received_content == b'%PDF-123'


def test_closing_boundary_split_across_chunks() -> None:
    app, ingest = _app()
    body = _multipart(b'%PDF-123')
    split = len(body) - 5
    status, _, _, _ = _asgi_request(app, [body[:split], body[split:]])
    assert status == HTTP_202_ACCEPTED
    assert ingest.received_content == b'%PDF-123'


@pytest.mark.parametrize('declared', [None, '1'])
def test_actual_bytes_reject_excess_without_trusting_length(
    declared: str | None,
) -> None:
    app, ingest = _app()
    body = _multipart(b'%PDF-123') + b'x' * MULTIPART_OVERHEAD_BYTES
    status, headers, response, delivered = _asgi_request(
        app, [body], content_length=declared
    )
    _assert_too_large(status, headers, response)
    assert delivered == 1
    assert ingest.command is None


def test_declared_excess_rejects_without_reading_body() -> None:
    app, ingest = _app()
    status, headers, response, delivered = _asgi_request(
        app,
        [_multipart(b'%PDF-123')],
        content_length=str(8 + MULTIPART_OVERHEAD_BYTES + 1),
    )
    _assert_too_large(status, headers, response)
    assert delivered == 0
    assert ingest.command is None
    metrics = generate_latest(app.state.metrics.registry)
    assert (
        b'docpipe_ingestion_validation_failures_total{reason="too_large"} 1.0'
    ) in metrics
    assert (
        b'docpipe_ingestion_uploads_total{outcome="rejected"} 1.0' in metrics
    )


def test_crossing_chunk_is_not_given_to_parser_and_spool_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, ingest = _app(max_file_size_bytes=2 * 1024 * 1024)
    created: list[SpooledTemporaryFile[bytes]] = []
    original_file = SpooledTemporaryFile
    original_write = UploadFile.write
    bytes_written = 0

    def track_file(*args: Any, **kwargs: Any) -> SpooledTemporaryFile[bytes]:
        file = original_file(*args, **kwargs)
        created.append(file)
        return file

    async def track_write(upload: UploadFile, data: bytes) -> None:
        nonlocal bytes_written
        bytes_written += len(data)
        await original_write(upload, data)

    monkeypatch.setattr(
        starlette.formparsers, 'SpooledTemporaryFile', track_file
    )
    monkeypatch.setattr(UploadFile, 'write', track_write)
    first = _multipart(b'%PDF-' + b'a' * (1024 * 1024 + 1), ending=b'')
    excess = b'x' * (2 * 1024 * 1024 + MULTIPART_OVERHEAD_BYTES)
    status, headers, response, delivered = _asgi_request(app, [first, excess])
    _assert_too_large(status, headers, response)
    assert delivered == len([first, excess])
    assert created
    assert all(file.closed for file in created)
    assert bytes_written == 5 + 1024 * 1024 + 1
    assert ingest.command is None


@pytest.mark.parametrize(
    'ending',
    [
        b'\r\n--wrong-boundary--\r\n',
        b'\r\n--' + BOUNDARY + b'\r\n',
    ],
)
def test_malformed_or_truncated_multipart_is_not_accepted(
    ending: bytes,
) -> None:
    app, ingest = _app()
    status, headers, response, _ = _asgi_request(
        app, [_multipart(b'%PDF-123', ending=ending)]
    )
    assert status == HTTP_400_BAD_REQUEST
    assert json.loads(response)['error']['code'] == 'invalid_request'
    assert headers['x-correlation-id'] == str(CORRELATION_ID)
    assert ingest.command is None


def test_disconnected_multipart_is_not_accepted() -> None:
    app, ingest = _app()
    body = _multipart(b'%PDF-123', ending=b'')
    status, headers, response, _ = _asgi_request(
        app, [body, b''], disconnect=True
    )
    assert status == HTTP_400_BAD_REQUEST
    assert json.loads(response)['error']['code'] == 'invalid_request'
    assert headers['x-correlation-id'] == str(CORRELATION_ID)
    assert ingest.command is None
