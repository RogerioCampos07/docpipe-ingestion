from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.dialects import sqlite

from docpipe_ingestion.infrastructure.database.base import UTCDateTime
from docpipe_ingestion.infrastructure.database.engine import (
    create_database_engine,
)
from docpipe_ingestion.infrastructure.settings import Settings

EXPECTED_BUSY_TIMEOUT_MS = 1_250


def test_sqlite_enables_foreign_keys_timeout_and_wal(
    tmp_path: Path,
) -> None:
    engine = create_database_engine(
        Settings(
            environment='test',
            database_url=f'sqlite:///{tmp_path / "configured.db"}',
            sqlite_timeout_seconds=1.25,
            sqlite_wal_enabled=True,
        )
    )

    try:
        with engine.connect() as connection:
            foreign_keys = connection.exec_driver_sql(
                'PRAGMA foreign_keys'
            ).scalar_one()
            busy_timeout = connection.exec_driver_sql(
                'PRAGMA busy_timeout'
            ).scalar_one()
            journal_mode = connection.exec_driver_sql(
                'PRAGMA journal_mode'
            ).scalar_one()
    finally:
        engine.dispose()

    assert foreign_keys == 1
    assert busy_timeout == EXPECTED_BUSY_TIMEOUT_MS
    assert journal_mode == 'wal'


def test_memory_database_does_not_require_wal() -> None:
    engine: Engine = create_database_engine(
        Settings(
            environment='test',
            database_url='sqlite:///:memory:',
            sqlite_wal_enabled=True,
        )
    )

    try:
        with engine.connect() as connection:
            journal_mode = connection.exec_driver_sql(
                'PRAGMA journal_mode'
            ).scalar_one()
    finally:
        engine.dispose()

    assert journal_mode == 'memory'


def test_sqlite_can_disable_wal(tmp_path: Path) -> None:
    engine = create_database_engine(
        Settings(
            environment='test',
            database_url=f'sqlite:///{tmp_path / "without-wal.db"}',
            sqlite_wal_enabled=False,
        )
    )

    try:
        with engine.connect() as connection:
            journal_mode = connection.exec_driver_sql(
                'PRAGMA journal_mode'
            ).scalar_one()
    finally:
        engine.dispose()

    assert journal_mode == 'delete'


def test_utc_database_type_rejects_naive_values_and_handles_none() -> None:
    utc_type = UTCDateTime()
    dialect = sqlite.dialect()

    assert utc_type.process_bind_param(None, dialect) is None
    assert utc_type.process_result_value(None, dialect) is None
    with pytest.raises(ValueError, match='timezone'):
        utc_type.process_bind_param(datetime(2026, 9, 17), dialect)
