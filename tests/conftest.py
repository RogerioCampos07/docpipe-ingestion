import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from docpipe_ingestion.infrastructure.database import models  # noqa: F401
from docpipe_ingestion.infrastructure.database.base import Base
from docpipe_ingestion.infrastructure.database.engine import (
    SessionFactory,
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.settings import Settings


def pytest_configure(config: pytest.Config) -> None:
    """Isolate settings before collection imports the application singleton."""
    isolation = pytest.MonkeyPatch()
    config.add_cleanup(isolation.undo)
    isolation.setitem(Settings.model_config, 'env_file', None)
    broker_integration = any(
        os.environ.get(name) == '1'
        for name in (
            'DOCPIPE_RABBITMQ_INTEGRATION',
            'DOCPIPE_STACK_INTEGRATION',
        )
    )
    for name in tuple(os.environ):
        if name.startswith('DOCPIPE_INGESTION_TEST_'):
            continue
        if broker_integration and name == 'DOCPIPE_INGESTION_RABBITMQ_URL':
            continue
        if name.startswith(('DOCPIPE_INGESTION_', 'OTEL_')):
            isolation.delenv(name)


@pytest.fixture(autouse=True)
def isolate_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    # Alembic fileConfig disables existing loggers in its test process.
    # Restore that state so later telemetry tests observe the real service.
    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            monkeypatch.setattr(logger, 'disabled', logger.disabled)


@pytest.fixture
def database_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_database_engine(
        Settings(
            environment='test',
            database_url=f'sqlite:///{tmp_path / "test.db"}',
            sqlite_wal_enabled=True,
        )
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(database_engine: Engine) -> SessionFactory:
    return create_session_factory(database_engine)
