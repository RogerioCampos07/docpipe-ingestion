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
    return os.environ.get(
        'DOCPIPE_INGESTION_TEST_POSTGRESQL_URL',
        'postgresql+psycopg://docpipe:docpipe-local@127.0.0.1:5432/'
        'docpipe_ingestion',
    )


@pytest.fixture
def azurite_connection_string() -> str:
    return os.environ.get(
        'DOCPIPE_INGESTION_TEST_AZURITE_CONNECTION_STRING',
        'DefaultEndpointsProtocol=http;AccountName=docpipe;'
        'AccountKey=ZG9jcGlwZS1sb2NhbC1vbmx5LW5vdC1zZWNyZXQ=;'
        'BlobEndpoint=http://127.0.0.1:10000/docpipe;',
    )
