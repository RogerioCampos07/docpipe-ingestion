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
