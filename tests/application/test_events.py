from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from docpipe_ingestion.application.events import DocumentReceivedV1


def _payload() -> dict[str, object]:
    event_id = '11111111-2222-3333-4444-555555555555'
    document_id = '12345678-1234-5678-1234-567812345678'
    return {
        'event_id': event_id,
        'event_type': 'document.received',
        'event_version': 1,
        'occurred_at': datetime(2026, 9, 17, 12, tzinfo=UTC),
        'correlation_id': '87654321-4321-8765-4321-876543218765',
        'document_id': document_id,
        'data': {
            'storage_key': f'{"a" * 32}.blob',
            'media_type': 'application/pdf',
            'size_bytes': 10,
            'sha256': 'b' * 64,
        },
    }


def test_document_received_v1_accepts_exact_contract() -> None:
    event = DocumentReceivedV1.model_validate(_payload())

    assert event.event_id == UUID('11111111-2222-3333-4444-555555555555')
    assert event.occurred_at.tzinfo is UTC
    assert set(event.data.model_dump()) == {
        'storage_key',
        'media_type',
        'size_bytes',
        'sha256',
    }


@pytest.mark.parametrize(
    'change',
    [
        {'event_version': 2},
        {'event_type': 'document.received.v2'},
        {'occurred_at': datetime(2026, 9, 17, 12)},
        {'secret': 'must not be accepted'},
    ],
)
def test_document_received_v1_rejects_invalid_envelope(
    change: dict[str, object],
) -> None:
    payload = _payload() | change

    with pytest.raises(ValidationError):
        DocumentReceivedV1.model_validate(payload)


def test_document_received_v1_rejects_extra_payload_data() -> None:
    payload = _payload()
    data_value = payload['data']
    assert isinstance(data_value, dict)
    data = dict(data_value)
    data['original_name'] = 'personal.pdf'
    payload['data'] = data

    with pytest.raises(ValidationError):
        DocumentReceivedV1.model_validate(payload)
