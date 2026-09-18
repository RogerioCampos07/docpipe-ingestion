import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from azure.core.exceptions import HttpResponseError
from azure.storage.blob import BlobServiceClient

from docpipe_ingestion.infrastructure.storage.azure_blob import (
    AzureBlobDocumentStorage,
    AzureBlobStorageConfig,
)

pytestmark = [
    pytest.mark.azurite,
    pytest.mark.skipif(
        os.environ.get('DOCPIPE_AZURITE_INTEGRATION') != '1',
        reason='set DOCPIPE_AZURITE_INTEGRATION=1',
    ),
]


def _storage(
    connection_string: str, container: str
) -> AzureBlobDocumentStorage:
    storage = AzureBlobDocumentStorage(
        AzureBlobStorageConfig(
            connection_string=connection_string,
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
    return storage


def test_two_adapters_share_private_streamed_object(
    azurite_connection_string: str,
) -> None:
    container = f'test-{uuid4().hex}'
    first = _storage(azurite_connection_string, container)
    second = _storage(azurite_connection_string, container)
    key = f'{uuid4().hex}.blob'
    content = b'%PDF-1.7\n' + (b'a' * 200_000)
    try:
        first.store(
            key,
            (
                content[index : index + 8192]
                for index in range(0, len(content), 8192)
            ),
        )
        assert key in second.list_keys()
        service = BlobServiceClient.from_connection_string(
            azurite_connection_string,
            api_version='2023-11-03',
        )
        blob = service.get_blob_client(container, key)
        assert blob.download_blob().readall() == content
        properties = blob.get_blob_properties()
        assert properties.content_settings.content_type == 'application/pdf'
        assert properties.metadata['size'] == str(len(content))
        assert (
            properties.metadata['sha256']
            == hashlib.sha256(content).hexdigest()
        )
        assert (
            first.list_incomplete(
                older_than=datetime.now(UTC) + timedelta(seconds=1)
            )
            == set()
        )
        with pytest.raises(HttpResponseError) as denied:
            BlobServiceClient(
                account_url='http://127.0.0.1:10000/docpipe',
                api_version='2023-11-03',
            ).get_blob_client(container, key).download_blob().readall()
        assert denied.value.status_code in {401, 403, 404}
        service.delete_container(container)
        service.close()
    finally:
        first.close()
        second.close()
