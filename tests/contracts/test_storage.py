import os
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest
from azure.storage.blob import BlobServiceClient

from docpipe_ingestion.application.ports import DocumentStorage
from docpipe_ingestion.infrastructure.storage.azure_blob import (
    AzureBlobDocumentStorage,
    AzureBlobStorageConfig,
)
from docpipe_ingestion.infrastructure.storage.local import LocalDocumentStorage


def _assert_storage_contract(
    storage: DocumentStorage,
    read: Callable[[str], bytes],
) -> None:
    key = f'{uuid4().hex}.blob'
    content = b'%PDF-1.7\ncontract document'
    storage.store(key, [content[:8], content[8:]])

    assert key in storage.list_keys()
    assert read(key) == content


def test_local_storage_contract(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')

    _assert_storage_contract(
        storage,
        lambda key: (storage.root / key).read_bytes(),
    )


@pytest.mark.azurite
@pytest.mark.skipif(
    os.environ.get('DOCPIPE_AZURITE_INTEGRATION') != '1',
    reason='set DOCPIPE_AZURITE_INTEGRATION=1',
)
def test_azurite_storage_contract() -> None:
    azurite_connection_string = os.environ.get(
        'DOCPIPE_INGESTION_TEST_AZURITE_CONNECTION_STRING',
    )
    if not azurite_connection_string:
        pytest.fail(
            'set DOCPIPE_INGESTION_TEST_AZURITE_CONNECTION_STRING '
            'to an isolated disposable test service'
        )
    container = f'contract-{uuid4().hex}'
    storage = AzureBlobDocumentStorage(
        AzureBlobStorageConfig(
            connection_string=azurite_connection_string,
            container=container,
            api_version='2023-11-03',
            connect_timeout=5,
            read_timeout=10,
            operation_timeout=30,
            retry_total=2,
            block_size=64 * 1024,
        )
    )
    storage.ensure_private_container()
    service = BlobServiceClient.from_connection_string(
        azurite_connection_string,
        api_version='2023-11-03',
    )
    try:
        _assert_storage_contract(
            storage,
            lambda key: (
                service
                .get_blob_client(container, key)
                .download_blob()
                .readall()
            ),
        )
    finally:
        service.delete_container(container)
        service.close()
        storage.close()
