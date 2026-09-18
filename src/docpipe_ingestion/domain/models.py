import math
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from docpipe_ingestion.domain.errors import (
    DomainValidationError,
    InvalidStatusTransitionError,
)

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)

_SHA256_PATTERN = re.compile(r'[0-9a-f]{64}')


class DocumentStatus(StrEnum):
    """Lifecycle states owned by the ingestion service."""

    RECEIVED = 'RECEIVED'
    STORED = 'STORED'
    PUBLISHED = 'PUBLISHED'
    FAILED = 'FAILED'


_ALLOWED_TRANSITIONS: dict[DocumentStatus, frozenset[DocumentStatus]] = {
    DocumentStatus.RECEIVED: frozenset({
        DocumentStatus.STORED,
        DocumentStatus.FAILED,
    }),
    DocumentStatus.STORED: frozenset({
        DocumentStatus.PUBLISHED,
        DocumentStatus.FAILED,
    }),
    DocumentStatus.PUBLISHED: frozenset(),
    DocumentStatus.FAILED: frozenset(),
}


def ensure_utc(value: datetime, *, field_name: str) -> datetime:
    """Return an aware UTC datetime or reject a naive value."""
    if value.tzinfo is None or value.utcoffset() is None:
        msg = f'{field_name} must include timezone information'
        raise DomainValidationError(msg)
    return value.astimezone(UTC)


def _validate_uuid(value: UUID, *, field_name: str) -> None:
    if not isinstance(value, UUID):
        msg = f'{field_name} must be a UUID'
        raise DomainValidationError(msg)


def _validate_json(value: JsonValue) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise DomainValidationError(
            'payload cannot contain non-finite numbers'
        )
    if isinstance(value, list):
        for item in value:
            _validate_json(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise DomainValidationError('payload keys must be strings')
            _validate_json(item)
        return
    raise DomainValidationError('payload contains a non-JSON value')


@dataclass(frozen=True, slots=True)
class Document:
    """Document metadata stored by the ingestion service."""

    id: UUID
    original_name: str
    media_type: str
    size_bytes: int
    sha256: str
    storage_key: str
    status: DocumentStatus
    correlation_id: UUID
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_uuid(self.id, field_name='id')
        _validate_uuid(self.correlation_id, field_name='correlation_id')
        if not self.original_name:
            raise DomainValidationError('original_name cannot be empty')
        if not self.media_type:
            raise DomainValidationError('media_type cannot be empty')
        if self.size_bytes <= 0:
            raise DomainValidationError('size_bytes must be positive')
        if _SHA256_PATTERN.fullmatch(self.sha256) is None:
            raise DomainValidationError(
                'sha256 must be a lowercase hexadecimal digest'
            )
        if not self.storage_key:
            raise DomainValidationError('storage_key cannot be empty')
        created_at = ensure_utc(self.created_at, field_name='created_at')
        updated_at = ensure_utc(self.updated_at, field_name='updated_at')
        if updated_at < created_at:
            raise DomainValidationError('updated_at cannot precede created_at')
        object.__setattr__(self, 'created_at', created_at)
        object.__setattr__(self, 'updated_at', updated_at)

    def transition_to(
        self,
        status: DocumentStatus,
        *,
        occurred_at: datetime,
    ) -> Document:
        """Create a document in the next valid lifecycle state."""
        if status not in _ALLOWED_TRANSITIONS[self.status]:
            msg = f'cannot transition document from {self.status} to {status}'
            raise InvalidStatusTransitionError(msg)
        updated_at = ensure_utc(occurred_at, field_name='occurred_at')
        if updated_at < self.updated_at:
            raise DomainValidationError(
                'transition time cannot precede updated_at'
            )
        return replace(self, status=status, updated_at=updated_at)


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    """Persisted event awaiting publication by a later stage."""

    id: UUID
    aggregate_id: UUID
    event_type: str
    payload: dict[str, JsonValue]
    created_at: datetime
    published_at: datetime | None = None
    attempts: int = 0
    last_error: str | None = None
    next_attempt_at: datetime | None = None
    trace_context: dict[str, str] | None = None

    def __post_init__(self) -> None:
        _validate_uuid(self.id, field_name='id')
        _validate_uuid(self.aggregate_id, field_name='aggregate_id')
        if not self.event_type:
            raise DomainValidationError('event_type cannot be empty')
        _validate_json(self.payload)
        if self.trace_context is not None:
            allowed = {'traceparent', 'tracestate'}
            if not set(self.trace_context) <= allowed:
                raise DomainValidationError(
                    'trace context contains unsafe keys'
                )
        created_at = ensure_utc(self.created_at, field_name='created_at')
        published_at = self.published_at
        next_attempt_at = self.next_attempt_at
        if published_at is not None:
            published_at = ensure_utc(
                published_at,
                field_name='published_at',
            )
            if published_at < created_at:
                raise DomainValidationError(
                    'published_at cannot precede created_at'
                )
        if self.attempts < 0:
            raise DomainValidationError('attempts cannot be negative')
        object.__setattr__(self, 'created_at', created_at)
        object.__setattr__(self, 'published_at', published_at)
        if next_attempt_at is not None:
            next_attempt_at = ensure_utc(
                next_attempt_at,
                field_name='next_attempt_at',
            )
        object.__setattr__(self, 'next_attempt_at', next_attempt_at)
