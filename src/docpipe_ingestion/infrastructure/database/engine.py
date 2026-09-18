from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from docpipe_ingestion.infrastructure.settings import Settings

type SessionFactory = sessionmaker[Session]


class DatabaseConfigurationError(RuntimeError):
    """Raised when SQLite cannot apply a required setting."""


def _is_file_sqlite(url: URL) -> bool:
    return url.get_backend_name() == 'sqlite' and url.database not in {
        None,
        '',
        ':memory:',
    }


def _create_database_parent(url: URL) -> None:
    if not _is_file_sqlite(url):
        return
    database = url.database
    if database is None:
        return
    Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def _configure_sqlite_connection(
    dbapi_connection: Any,
    connection_record: Any,
    *,
    busy_timeout_ms: int,
) -> None:
    del connection_record
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute(f'PRAGMA busy_timeout={busy_timeout_ms:d}')
    finally:
        cursor.close()


def create_database_engine(settings: Settings) -> Engine:
    """Create an engine with the required SQLite safety settings."""
    url = make_url(settings.database_url)
    _create_database_parent(url)
    connect_args: dict[str, object] = {}
    if url.get_backend_name() == 'sqlite':
        connect_args = {
            'check_same_thread': False,
            'timeout': settings.sqlite_timeout_seconds,
        }
    engine_options: dict[str, object] = {'connect_args': connect_args}
    if settings.database_backend == 'postgresql':
        connect_args = {
            'connect_timeout': settings.postgres_connect_timeout_seconds,
            'options': (
                '-c statement_timeout='
                f'{settings.postgres_statement_timeout_ms} '
                f'-c lock_timeout={settings.postgres_lock_timeout_ms}'
            ),
        }
        engine_options = {
            'connect_args': connect_args,
            'pool_pre_ping': True,
            'pool_size': settings.postgres_pool_size,
            'max_overflow': settings.postgres_max_overflow,
            'pool_timeout': settings.postgres_pool_timeout_seconds,
            'hide_parameters': True,
        }
    engine = create_engine(url, **engine_options)
    if url.get_backend_name() != 'sqlite':
        return engine

    busy_timeout_ms = round(settings.sqlite_timeout_seconds * 1000)

    @event.listens_for(engine, 'connect')
    def configure_connection(
        dbapi_connection: Any,
        connection_record: Any,
    ) -> None:
        _configure_sqlite_connection(
            dbapi_connection,
            connection_record,
            busy_timeout_ms=busy_timeout_ms,
        )

    if settings.sqlite_wal_enabled and _is_file_sqlite(url):
        with engine.connect() as connection:
            journal_mode = connection.exec_driver_sql(
                'PRAGMA journal_mode=WAL'
            ).scalar_one()
        if str(journal_mode).lower() != 'wal':
            engine.dispose()
            msg = f'SQLite could not enable WAL mode: {journal_mode!r}'
            raise DatabaseConfigurationError(msg)
    return engine


def create_session_factory(engine: Engine) -> SessionFactory:
    """Create sessions with explicit transaction lifetimes."""
    return sessionmaker(bind=engine, expire_on_commit=False)
