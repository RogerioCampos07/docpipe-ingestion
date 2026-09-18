from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from uuid import UUID, uuid4

_correlation_id: ContextVar[UUID | None] = ContextVar(
    'correlation_id', default=None
)


def current_correlation_id() -> UUID | None:
    return _correlation_id.get()


def set_correlation_id(value: UUID) -> Token[UUID | None]:
    return _correlation_id.set(value)


def reset_correlation_id(token: Token[UUID | None]) -> None:
    _correlation_id.reset(token)


@contextmanager
def correlated(value: UUID | None = None) -> Iterator[UUID]:
    correlation_id = value or uuid4()
    token = set_correlation_id(correlation_id)
    try:
        yield correlation_id
    finally:
        reset_correlation_id(token)
