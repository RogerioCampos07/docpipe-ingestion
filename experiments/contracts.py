"""Validate the public response without depending on Locust or networking."""

from datetime import UTC, datetime
from uuid import UUID

from experiments.fixtures import Fixture


def _uuid(value: object) -> UUID:
    if not isinstance(value, str):
        raise ValueError('expected UUID string')
    return UUID(value)


def accepted(body: object, correlation: str | None) -> tuple[UUID, UUID]:
    if not isinstance(body, dict):
        raise ValueError('acceptance response is not an object')
    document_id = _uuid(body.get('document_id'))
    correlation_id = _uuid(body.get('correlation_id'))
    if body.get('status') != 'STORED':
        raise ValueError('acceptance status is not STORED')
    if correlation != str(correlation_id):
        raise ValueError('correlation header differs from body')
    if not isinstance(body.get('received_at'), str):
        raise ValueError('acceptance time is missing')
    timestamp = datetime.fromisoformat(
        body['received_at'].replace('Z', '+00:00')
    )
    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(
        None
    ):
        raise ValueError('acceptance time is not UTC')
    return document_id, correlation_id


def metadata(
    body: object,
    *,
    document_id: UUID,
    name: str,
    fixture: Fixture,
    correlation_id: UUID,
) -> None:
    if not isinstance(body, dict):
        raise ValueError('metadata response is not an object')
    expected = {
        'document_id': str(document_id),
        'original_name': name,
        'media_type': fixture.media_type,
        'size_bytes': len(fixture.data),
        'sha256': fixture.sha256,
        'correlation_id': str(correlation_id),
    }
    if any(body.get(key) != value for key, value in expected.items()):
        raise ValueError('metadata differs from accepted fixture')
    if body.get('status') not in {'STORED', 'PUBLISHED'}:
        raise ValueError('metadata status is invalid')
    if any(key in body for key in ('storage_key', 'storage_url', 'file')):
        raise ValueError('response exposes storage details')


def error_response(body: object, correlation: str | None) -> str:
    if not isinstance(body, dict) or not isinstance(body.get('error'), dict):
        raise ValueError('error response is not structured')
    details = body['error']
    if not isinstance(details.get('code'), str):
        raise ValueError('error code is missing')
    if not isinstance(details.get('message'), str):
        raise ValueError('error message is missing')
    if str(_uuid(details.get('correlation_id'))) != correlation:
        raise ValueError('error correlation differs from header')
    return str(details['code'])
