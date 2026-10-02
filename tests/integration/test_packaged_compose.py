"""Exercise the built image against an isolated official Compose stack."""

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

import pika  # type: ignore[import-untyped]
import pytest
from azure.storage.blob import BlobServiceClient, ContainerClient
from pika.adapters.blocking_connection import (  # type: ignore[import-untyped]
    BlockingChannel,
    BlockingConnection,
)
from sqlalchemy import Engine, create_engine, func, select, text, update
from sqlalchemy.orm import Session

from docpipe_ingestion.infrastructure.database.models import (
    DocumentModel,
    OutboxEventModel,
)

pytestmark = [
    pytest.mark.packaged,
    pytest.mark.skipif(
        os.environ.get('DOCPIPE_PACKAGED_IMAGE_INTEGRATION') != '1',
        reason='set DOCPIPE_PACKAGED_IMAGE_INTEGRATION=1',
    ),
]

_FORMATS = (
    ('sample.pdf', 'application/pdf', b'%PDF-1.7\nsynthetic PDF'),
    ('sample.png', 'image/png', b'\x89PNG\r\n\x1a\nsynthetic PNG'),
    ('sample.jpg', 'image/jpeg', b'\xff\xd8\xffsynthetic JPEG'),
)
_MAX_ATTEMPTS = 5
_PERSISTENT_DELIVERY_MODE = 2
_REJECTED_UPLOAD_MARKERS = 2
_RABBITMQ_CONNECT_TIMEOUT_SECONDS = 45


@dataclass
class PackagedStack:
    engine: Engine
    blob_service: BlobServiceClient
    container: ContainerClient
    rabbit: BlockingConnection
    channel: BlockingChannel
    image_id: str
    unacked_message_ids: set[str] = field(default_factory=set)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.fail(f'{name} must identify an isolated Compose test target')
    return value


def _compose(*arguments: str, timeout: int = 180) -> str:
    project = _required('CI_COMPOSE_PROJECT')
    image = _required('CI_IMAGE')
    root = Path(__file__).parents[2]
    environment = os.environ.copy()
    environment['DOCPIPE_INGESTION_IMAGE'] = image
    result = subprocess.run(
        [
            'docker',
            'compose',
            '--project-name',
            project,
            '--env-file',
            '/dev/null',
            '--file',
            'docker-compose.yml',
            *arguments,
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise AssertionError(
            f'docker compose {" ".join(arguments)} failed:\n'
            f'{result.stdout}\n{result.stderr}'
        )
    return result.stdout.strip()


def _run_packaged_module(module: str, *arguments: str) -> str:
    """Run an application command in the image, without checkout mounts."""
    return _compose(
        '--profile',
        'setup',
        'run',
        '--rm',
        '--no-deps',
        'setup',
        'python',
        '-m',
        module,
        *arguments,
        timeout=60,
    )


def _docker(*arguments: str, timeout: int = 20) -> str:
    result = subprocess.run(
        ['docker', *arguments],
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise AssertionError(
            f'docker {" ".join(arguments)} failed:\n'
            f'{result.stdout}\n{result.stderr}'
        )
    return result.stdout.strip()


def _request(
    method: str, path: str, body: bytes | None = None
) -> tuple[int, bytes]:
    request = Request(
        f'{_required("CI_API_URL")}{path}',
        data=body,
        method=method,
        headers=(
            {'Content-Type': 'application/json'}
            if body is not None and method == 'POST'
            else {}
        ),
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()
    except URLError as error:
        raise AssertionError(
            f'HTTP request to {path} failed: {error}'
        ) from error


def _post_document_response(
    filename: str,
    media_type: str,
    content: bytes,
) -> tuple[int, bytes]:
    boundary = f'docpipe-{UUID(int=int(time.time_ns()))}'
    body = b''.join((
        f'--{boundary}\r\n'.encode(),
        (
            'Content-Disposition: form-data; name="file"; '
            f'filename="{filename}"\r\n'
        ).encode(),
        f'Content-Type: {media_type}\r\n\r\n'.encode(),
        content,
        f'\r\n--{boundary}--\r\n'.encode(),
    ))
    request = Request(
        f'{_required("CI_API_URL")}/v1/documents',
        data=body,
        method='POST',
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def _post_document(
    filename: str,
    media_type: str,
    content: bytes,
) -> UUID:
    status, response = _post_document_response(filename, media_type, content)
    assert status == HTTPStatus.ACCEPTED, response
    result = json.loads(response)
    return UUID(result['document_id'])


def _database_url() -> str:
    return _required('DOCPIPE_INGESTION_TEST_POSTGRESQL_URL')


def _blob_connection_string() -> str:
    return _required('DOCPIPE_INGESTION_TEST_AZURITE_CONNECTION_STRING')


def _rabbitmq_url() -> str:
    return _required('DOCPIPE_INGESTION_RABBITMQ_URL')


def _open_rabbitmq() -> BlockingConnection:
    parameters = pika.URLParameters(_rabbitmq_url())
    parameters.socket_timeout = 2
    parameters.stack_timeout = 5
    parameters.blocked_connection_timeout = 5
    deadline = time.monotonic() + _RABBITMQ_CONNECT_TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return pika.BlockingConnection(parameters)
        except Exception as error:
            last_error = error
            time.sleep(0.5)
    raise AssertionError(
        'RabbitMQ did not accept an AMQP connection before the deadline'
    ) from last_error


def _close_rabbitmq(connection: BlockingConnection) -> None:
    try:
        if connection.is_open:
            connection.close()
    except Exception:
        pass


def _open_stack() -> PackagedStack:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    blob_service = BlobServiceClient.from_connection_string(
        _blob_connection_string(), retry_total=0
    )
    container = blob_service.get_container_client('documents')
    rabbit = _open_rabbitmq()
    image_id = _docker(
        'image', 'inspect', '--format', '{{.Id}}', _required('CI_IMAGE')
    )
    return PackagedStack(
        engine=engine,
        blob_service=blob_service,
        container=container,
        rabbit=rabbit,
        channel=rabbit.channel(),
        image_id=image_id,
    )


def _close_stack(stack: PackagedStack) -> None:
    _close_rabbitmq(stack.rabbit)
    stack.blob_service.close()
    stack.engine.dispose()


def _document_and_event(
    session: Session,
    document_id: UUID,
) -> tuple[DocumentModel, OutboxEventModel]:
    document = session.get(DocumentModel, document_id)
    event = session.scalar(
        select(OutboxEventModel).where(
            OutboxEventModel.aggregate_id == document_id
        )
    )
    assert document is not None
    assert event is not None
    assert event.payload['document_id'] == str(document_id)
    assert event.payload['event_id'] == str(event.id)
    assert event.aggregate_id == document.id
    return document, event


def _wait_published(engine: Engine, document_id: UUID) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        with Session(engine) as session:
            document = session.get(DocumentModel, document_id)
            if document is not None and document.status == 'PUBLISHED':
                return
        time.sleep(0.25)
    raise AssertionError(f'worker did not publish document {document_id}')


def _wait_exhausted(engine: Engine, event_id: UUID) -> OutboxEventModel:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        with Session(engine) as session:
            event = session.get(OutboxEventModel, event_id)
            if (
                event is not None
                and event.attempts >= _MAX_ATTEMPTS
                and event.published_at is None
            ):
                return event
        time.sleep(0.25)
    raise AssertionError(f'worker did not exhaust outbox event {event_id}')


def _worker_state() -> tuple[str, int]:
    container_id = _compose('ps', '--all', '-q', 'worker')
    assert container_id
    state = json.loads(
        _docker('inspect', '--format', '{{json .State}}', container_id)
    )
    return state['Status'], state['ExitCode']


def _wait_worker_exited() -> int:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        status, exit_code = _worker_state()
        if status == 'exited':
            return exit_code
        time.sleep(0.25)
    raise AssertionError('worker remained running after losing RabbitMQ')


def _wait_http_status(url: str, expected: int, timeout: int = 45) -> None:
    deadline = time.monotonic() + timeout
    last_status: int | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                last_status = response.status
        except HTTPError as error:
            last_status = error.code
        except URLError:
            last_status = None
        except OSError:
            last_status = None
        if last_status == expected:
            return
        time.sleep(0.25)
    raise AssertionError(f'{url} did not return {expected}; got {last_status}')


def _set_next_attempt(
    engine: Engine,
    event_id: UUID,
    value: datetime | None,
) -> None:
    with Session(engine) as session:
        session.execute(
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .values(next_attempt_at=value)
        )
        session.commit()


def _message(
    channel: BlockingChannel,
) -> tuple[
    pika.spec.BasicProperties,
    dict[str, object],
]:
    method, properties, body = channel.basic_get(
        queue='docpipe.document.received.v1',
        auto_ack=True,
    )
    assert method is not None
    assert properties is not None
    return properties, json.loads(body)


def _start_worker() -> None:
    _compose(
        'up',
        '-d',
        '--no-build',
        '--wait',
        '--wait-timeout',
        '120',
        'worker',
    )
    _wait_http_status('http://127.0.0.1:19001/health/ready', 200)


def _verify_image_container(service: str, image_id: str) -> None:
    container_id = _compose('ps', '-q', service)
    assert container_id
    assert (
        _docker('inspect', '--format', '{{.Config.User}}', container_id)
        == '10001:10001'
    )
    assert (
        _docker('inspect', '--format', '{{.Image}}', container_id) == image_id
    )
    mounts = json.loads(
        _docker('inspect', '--format', '{{json .Mounts}}', container_id)
    )
    assert mounts == [], 'application image must not receive checkout mounts'


def _check_message(
    channel: BlockingChannel,
    expected_event_id: UUID,
    expected_document_id: UUID,
    expected_correlation_id: str,
) -> dict[str, object]:
    properties, payload = _message(channel)
    assert properties.message_id == str(expected_event_id)
    assert properties.type == 'document.received.v1'
    assert properties.content_type == 'application/json'
    assert properties.delivery_mode == _PERSISTENT_DELIVERY_MODE
    assert properties.correlation_id == expected_correlation_id
    assert payload['event_id'] == str(expected_event_id)
    assert payload['document_id'] == str(expected_document_id)
    assert payload['event_type'] == 'document.received'
    assert payload['event_version'] == 1
    return payload


def _submit_files(
    stack: PackagedStack,
) -> list[tuple[UUID, str, str, bytes]]:
    with Session(stack.engine) as session:
        before_events = session.scalar(
            select(func.count()).select_from(OutboxEventModel)
        )
    assert before_events is not None
    before_storage_keys = {
        item.name
        for item in stack.container.list_blobs()
        if not item.name.startswith('_uploads/')
    }
    before_incomplete_keys = {
        item.name
        for item in stack.container.list_blobs(name_starts_with='_uploads/')
    }
    accepted = [
        (_post_document(*file_data), *file_data) for file_data in _FORMATS
    ]
    accepted.append((_post_document(*_FORMATS[0]), *_FORMATS[0]))

    status, _ = _post_document_response(
        'invalid.txt', 'text/plain', b'not a supported document'
    )
    assert status == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    status, _ = _post_document_response('empty.pdf', 'application/pdf', b'')
    assert status == HTTPStatus.BAD_REQUEST
    status, _ = _request('POST', '/v1/documents', b'{"not":"multipart"}')
    assert status == HTTPStatus.BAD_REQUEST
    with Session(stack.engine) as session:
        after_events = session.scalar(
            select(func.count()).select_from(OutboxEventModel)
        )
    assert after_events is not None
    assert after_events == before_events + len(accepted)
    after_storage_keys = {
        item.name
        for item in stack.container.list_blobs()
        if not item.name.startswith('_uploads/')
    }
    assert len(after_storage_keys - before_storage_keys) == len(accepted)
    after_incomplete_keys = {
        item.name
        for item in stack.container.list_blobs(name_starts_with='_uploads/')
    }
    assert (
        len(after_incomplete_keys - before_incomplete_keys)
        == _REJECTED_UPLOAD_MARKERS
    )
    return accepted


def _verify_expected_messages(
    stack: PackagedStack,
    records: list[tuple[DocumentModel, OutboxEventModel]],
    *,
    retain_event_ids: set[str] | None = None,
) -> None:
    retain = retain_event_ids or set()
    queue = stack.channel.queue_declare(
        queue='docpipe.document.received.v1',
        passive=True,
    )
    assert queue.method.consumer_count == 0
    expected = {
        str(event.id): (document, event) for document, event in records
    }
    remaining = len(set(expected) | retain)
    seen: set[str] = set()
    for _ in range(remaining):
        method, properties, body = stack.channel.basic_get(
            queue='docpipe.document.received.v1',
            auto_ack=False,
        )
        assert method is not None
        assert properties is not None
        assert properties.message_id is not None
        event_id = properties.message_id
        assert event_id in expected or event_id in retain
        if event_id in expected:
            document, event = expected[event_id]
            assert document is not None
            assert event is not None
            payload = json.loads(body)
            assert event.published_at is not None
            assert properties.type == 'document.received.v1'
            assert properties.content_type == 'application/json'
            assert properties.delivery_mode == _PERSISTENT_DELIVERY_MODE
            assert properties.correlation_id == event.payload['correlation_id']
            assert payload == event.payload
            assert payload['document_id'] == str(document.id)
            seen.add(event_id)
        if event_id not in retain:
            stack.channel.basic_ack(method.delivery_tag)
    assert seen == set(expected)
    stack.unacked_message_ids = retain.copy()


def _record_for_document(
    engine: Engine,
    document_id: UUID,
) -> tuple[DocumentModel, OutboxEventModel]:
    with Session(engine) as session:
        return _document_and_event(session, document_id)


def _record_for_event(
    engine: Engine,
    event_id: UUID,
) -> tuple[DocumentModel, OutboxEventModel]:
    with Session(engine) as session:
        event = session.get(OutboxEventModel, event_id)
        assert event is not None
        return _document_and_event(session, event.aggregate_id)


def _verify_initial_publication(
    stack: PackagedStack,
    accepted: list[tuple[UUID, str, str, bytes]],
) -> None:
    with Session(stack.engine) as session:
        pending = [_document_and_event(session, item[0]) for item in accepted]
        assert all(document.status == 'STORED' for document, _ in pending)
        assert all(event.published_at is None for _, event in pending)

    _start_worker()
    _verify_image_container('api', stack.image_id)
    _verify_image_container('worker', stack.image_id)
    for document_id, _, _, _ in accepted:
        _wait_published(stack.engine, document_id)

    with Session(stack.engine) as session:
        records = [_document_and_event(session, item[0]) for item in accepted]
        assert all(event.published_at is not None for _, event in records)
        assert len({doc.storage_key for doc, _ in records}) == len(accepted)
        assert len({event.id for _, event in records}) == len(accepted)
        assert records[0][0].sha256 == records[-1][0].sha256
        assert records[0][0].id != records[-1][0].id

    assert stack.container.get_container_properties().public_access is None
    for accepted_record, (document, event) in zip(
        accepted,
        records,
        strict=True,
    ):
        document_id, _, _, content = accepted_record
        assert document.id == document_id
        assert document.size_bytes == len(content)
        assert document.sha256 == hashlib.sha256(content).hexdigest()
        blob = stack.container.get_blob_client(document.storage_key)
        assert blob.download_blob().readall() == content
        assert event.payload['data']['sha256'] == document.sha256
        assert event.payload['data']['storage_key'] == document.storage_key
        status, response = _request('GET', f'/v1/documents/{document_id}')
        assert status == HTTPStatus.OK
        projection = json.loads(response)
        assert projection['status'] == 'PUBLISHED'
        assert 'storage_key' not in projection

    _verify_expected_messages(
        stack,
        records,
        retain_event_ids={str(records[0][1].id)},
    )


def _verify_channel_recovery(stack: PackagedStack) -> list[UUID]:
    _compose('stop', 'worker')
    retained_message_ids = stack.unacked_message_ids.copy()
    _close_rabbitmq(stack.rabbit)
    stack.unacked_message_ids.clear()
    recover_id = _post_document(
        'resume.pdf', 'application/pdf', _FORMATS[0][2]
    )
    recover_event = _record_for_document(stack.engine, recover_id)[1]
    _set_next_attempt(
        stack.engine,
        recover_event.id,
        datetime.now(UTC) + timedelta(hours=1),
    )
    _start_worker()
    _compose('stop', 'rabbitmq')

    broker_down_id = _post_document(
        'broker-down.pdf', 'application/pdf', _FORMATS[0][2]
    )
    assert _request('GET', '/health/ready')[0] == HTTPStatus.OK
    assert _wait_worker_exited() != 0
    logs = _compose('logs', '--no-color', '--tail', '100', 'worker')
    assert 'channel_unavailable' in logs

    records = [
        _record_for_document(stack.engine, document_id)
        for document_id in (recover_id, broker_down_id)
    ]
    assert all(event.published_at is None for _, event in records)
    assert all(event.attempts == 0 for _, event in records)

    _compose(
        'up',
        '-d',
        '--no-build',
        '--wait',
        '--wait-timeout',
        '150',
        'rabbitmq',
    )
    _close_rabbitmq(stack.rabbit)
    stack.rabbit = _open_rabbitmq()
    stack.channel = stack.rabbit.channel()
    _set_next_attempt(stack.engine, recover_event.id, None)
    _compose('start', 'worker')
    _wait_http_status('http://127.0.0.1:19001/health/ready', HTTPStatus.OK)
    for document_id in (recover_id, broker_down_id):
        _wait_published(stack.engine, document_id)
    records = [
        _record_for_document(stack.engine, document_id)
        for document_id in (recover_id, broker_down_id)
    ]
    assert all(event.published_at is not None for _, event in records)
    _verify_expected_messages(
        stack,
        records,
        retain_event_ids=retained_message_ids,
    )
    return [recover_id, broker_down_id]


def _verify_requeue(stack: PackagedStack) -> UUID:
    retained_message_ids = stack.unacked_message_ids.copy()
    stack.channel.queue_unbind(
        queue='docpipe.document.received.v1',
        exchange='docpipe.events',
        routing_key='document.received.v1',
    )
    document_id = _post_document(
        'exhausted.pdf', 'application/pdf', _FORMATS[0][2]
    )
    with Session(stack.engine) as session:
        _, event = _document_and_event(session, document_id)
        session.commit()
        event_id = event.id
        original_payload = dict(event.payload)

    exhausted = _wait_exhausted(stack.engine, event_id)
    assert exhausted.last_error == 'BrokerPublishError'
    exhausted_error = exhausted.last_error
    _wait_http_status('http://127.0.0.1:19001/health/ready', HTTPStatus.OK)
    _compose('stop', 'worker')
    stack.channel.queue_bind(
        queue='docpipe.document.received.v1',
        exchange='docpipe.events',
        routing_key='document.received.v1',
    )
    result = _run_packaged_module(
        'docpipe_ingestion.requeue_event', str(event_id)
    )
    assert str(event_id) in result
    requeued = _record_for_document(stack.engine, document_id)[1]
    assert requeued.attempts == 0
    assert requeued.last_error == exhausted_error
    assert requeued.payload == original_payload

    _compose('start', 'worker')
    _wait_http_status('http://127.0.0.1:19001/health/ready', HTTPStatus.OK)
    _wait_published(stack.engine, document_id)
    record = _record_for_document(stack.engine, document_id)
    _verify_expected_messages(
        stack,
        [record],
        retain_event_ids=retained_message_ids | {str(event_id)},
    )
    return document_id


def _create_and_reconcile_orphan(stack: PackagedStack) -> str:
    with Session(stack.engine) as session:
        before_documents = session.scalar(
            select(func.count()).select_from(DocumentModel)
        )
        before_events = session.scalar(
            select(func.count()).select_from(OutboxEventModel)
        )
    assert before_documents is not None
    assert before_events is not None
    before_blobs = {item.name for item in stack.container.list_blobs()}
    incomplete_keys = {
        item.name
        for item in stack.container.list_blobs(name_starts_with='_uploads/')
    }
    with stack.engine.begin() as connection:
        connection.execute(
            text(
                """CREATE FUNCTION docpipe_ci_reject_document()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'synthetic metadata persistence failure';
            END;
            $$"""
            )
        )
        connection.execute(
            text(
                """CREATE TRIGGER docpipe_ci_reject_document
            BEFORE INSERT ON documents
            FOR EACH ROW EXECUTE FUNCTION docpipe_ci_reject_document()"""
            )
        )
    try:
        status, response = _post_document_response(
            'database-failure.pdf', 'application/pdf', _FORMATS[0][2]
        )
        assert status == HTTPStatus.SERVICE_UNAVAILABLE, response
        assert json.loads(response)['error']['code'] == (
            'persistence_unavailable'
        )
    finally:
        with stack.engine.begin() as connection:
            connection.execute(
                text(
                    'DROP TRIGGER IF EXISTS docpipe_ci_reject_document '
                    'ON documents'
                )
            )
            connection.execute(
                text('DROP FUNCTION IF EXISTS docpipe_ci_reject_document()')
            )

    with Session(stack.engine) as session:
        after_documents = session.scalar(
            select(func.count()).select_from(DocumentModel)
        )
        after_events = session.scalar(
            select(func.count()).select_from(OutboxEventModel)
        )
    assert after_documents == before_documents
    assert after_events == before_events
    new_blobs = {
        item.name for item in stack.container.list_blobs()
    } - before_blobs
    assert len(new_blobs) == 1
    orphan_key = new_blobs.pop()
    result = json.loads(
        _run_packaged_module('docpipe_ingestion.reconcile_storage')
    )
    assert orphan_key in result['orphaned_keys']
    assert incomplete_keys <= set(result['incomplete_keys'])
    assert stack.container.get_blob_client(orphan_key).exists()
    return orphan_key


def _recreate_stack_and_verify_persistence(
    stack: PackagedStack,
    persisted_ids: list[UUID],
    pending_restart_id: UUID,
    orphan_key: str,
) -> None:
    _compose('stop', 'worker')
    persisted_message_ids = stack.unacked_message_ids.copy()
    _close_rabbitmq(stack.rabbit)
    stack.unacked_message_ids.clear()
    _compose('down', '--remove-orphans')
    _compose(
        'up',
        '-d',
        '--no-build',
        '--wait',
        '--wait-timeout',
        '120',
        'postgres',
        'azurite',
    )
    _compose(
        'up',
        '-d',
        '--no-build',
        '--wait',
        '--wait-timeout',
        '150',
        'rabbitmq',
    )
    _compose('--profile', 'setup', 'run', '--rm', 'setup')
    pending_event = _record_for_document(stack.engine, pending_restart_id)[1]
    assert pending_event.published_at is None
    _set_next_attempt(stack.engine, pending_event.id, None)
    _compose(
        'up',
        '-d',
        '--no-build',
        '--wait',
        '--wait-timeout',
        '120',
        'api',
        'worker',
    )
    stack.rabbit = _open_rabbitmq()
    stack.channel = stack.rabbit.channel()
    _wait_http_status(f'{_required("CI_API_URL")}/health/ready', HTTPStatus.OK)
    _wait_published(stack.engine, pending_restart_id)

    with Session(stack.engine) as session:
        for document_id in persisted_ids:
            document = session.get(DocumentModel, document_id)
            assert document is not None
            assert document.status == 'PUBLISHED'
        _, pending_event = _document_and_event(session, pending_restart_id)
        assert pending_event.published_at is not None
        pending_event_id = pending_event.id

    for document_id in persisted_ids:
        status, response = _request('GET', f'/v1/documents/{document_id}')
        assert status == HTTPStatus.OK
        assert json.loads(response)['status'] == 'PUBLISHED'
    first_document = _record_for_document(stack.engine, persisted_ids[0])[0]
    blob = stack.container.get_blob_client(first_document.storage_key)
    assert blob.download_blob().readall() == _FORMATS[0][2]
    assert stack.container.get_blob_client(orphan_key).exists()

    persisted_messages = [
        _record_for_event(stack.engine, UUID(event_id))
        for event_id in persisted_message_ids
    ]
    persisted_messages.append(
        _record_for_event(stack.engine, pending_event_id)
    )
    _verify_expected_messages(stack, persisted_messages)


def test_packaged_compose_flow_failure_recovery_requeue_and_restart() -> None:
    """Verify real HTTP, broker, database, blob and container restart paths."""
    stack = _open_stack()
    try:
        _wait_http_status(
            f'{_required("CI_API_URL")}/health/ready', HTTPStatus.OK
        )
        accepted = _submit_files(stack)
        _verify_initial_publication(stack, accepted)
        recovered_ids = _verify_channel_recovery(stack)
        requeued_id = _verify_requeue(stack)
        _compose('stop', 'worker')
        pending_restart_id = _post_document(
            'restart.pdf', 'application/pdf', _FORMATS[0][2]
        )
        pending_event = _record_for_document(stack.engine, pending_restart_id)[
            1
        ]
        assert pending_event.published_at is None
        _set_next_attempt(
            stack.engine,
            pending_event.id,
            datetime.now(UTC) + timedelta(hours=1),
        )
        orphan_key = _create_and_reconcile_orphan(stack)
        _recreate_stack_and_verify_persistence(
            stack,
            [item[0] for item in accepted] + recovered_ids + [requeued_id],
            pending_restart_id,
            orphan_key,
        )
    finally:
        _close_stack(stack)
