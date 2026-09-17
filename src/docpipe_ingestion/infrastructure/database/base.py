from datetime import UTC, datetime
from typing import override

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    """Declarative base shared by the current database schema."""


class UTCDateTime(TypeDecorator[datetime]):
    """Store naive UTC in SQLite and expose aware UTC to the domain."""

    impl = DateTime
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('database datetime must include a timezone')
        return value.astimezone(UTC).replace(tzinfo=None)

    @override
    def process_result_value(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        del dialect
        if value is None:
            return None
        return value.replace(tzinfo=UTC)
