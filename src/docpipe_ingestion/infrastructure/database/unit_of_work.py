from types import TracebackType

from sqlalchemy.orm import Session

from docpipe_ingestion.infrastructure.database.engine import SessionFactory
from docpipe_ingestion.infrastructure.database.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyOutboxEventRepository,
)


class SqlAlchemyUnitOfWork:
    """Coordinate repositories in one SQLAlchemy transaction."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._documents: SqlAlchemyDocumentRepository | None = None
        self._outbox_events: SqlAlchemyOutboxEventRepository | None = None

    @property
    def documents(self) -> SqlAlchemyDocumentRepository:
        if self._documents is None:
            raise RuntimeError('unit of work has not been entered')
        return self._documents

    @property
    def outbox_events(self) -> SqlAlchemyOutboxEventRepository:
        if self._outbox_events is None:
            raise RuntimeError('unit of work has not been entered')
        return self._outbox_events

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        if self._session is not None:
            raise RuntimeError('unit of work cannot be entered twice')
        self._session = self._session_factory()
        self._documents = SqlAlchemyDocumentRepository(self._session)
        self._outbox_events = SqlAlchemyOutboxEventRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        if self._session is None:
            return
        try:
            self._session.rollback()
        finally:
            self._session.close()
            self._session = None
            self._documents = None
            self._outbox_events = None

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError('unit of work has not been entered')
        self._session.commit()

    def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError('unit of work has not been entered')
        self._session.rollback()
