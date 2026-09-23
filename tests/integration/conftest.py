import os

import pytest
from alembic import command
from alembic.config import Config


def integration_enabled(name: str) -> bool:
    return os.environ.get(name) == '1'


def migrate(database_url: str) -> None:
    config = Config('alembic.ini')
    config.set_main_option('sqlalchemy.url', database_url)
    command.upgrade(config, 'head')


@pytest.fixture
def postgresql_url() -> str:
    return _explicit_target('DOCPIPE_INGESTION_TEST_POSTGRESQL_URL')


@pytest.fixture
def azurite_connection_string() -> str:
    return _explicit_target('DOCPIPE_INGESTION_TEST_AZURITE_CONNECTION_STRING')


@pytest.fixture
def rabbitmq_url() -> str:
    return _explicit_target('DOCPIPE_INGESTION_RABBITMQ_URL')


def _explicit_target(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.fail(f'set {name} to an isolated disposable test service')
    return value
