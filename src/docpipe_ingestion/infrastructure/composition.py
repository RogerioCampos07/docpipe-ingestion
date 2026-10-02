"""Configuration-driven construction of infrastructure adapters."""

from docpipe_ingestion.application.ports import DocumentStorage
from docpipe_ingestion.infrastructure.settings import Settings
from docpipe_ingestion.infrastructure.storage.azure_blob import (
    AzureBlobDocumentStorage,
    AzureBlobStorageConfig,
)
from docpipe_ingestion.infrastructure.storage.local import LocalDocumentStorage


def create_document_storage(settings: Settings) -> DocumentStorage:
    if settings.storage_backend == 'local':
        return LocalDocumentStorage(settings.storage_root)
    storage = create_azure_blob_storage(settings)
    storage.ensure_private_container()
    return storage


def create_azure_blob_storage(
    settings: Settings,
) -> AzureBlobDocumentStorage:
    """Construct the Azurite adapter without creating remote resources."""
    if settings.storage_backend != 'azurite':
        raise ValueError('Azure blob storage requires the azurite backend')
    connection_string = settings.blob_connection_string
    if connection_string is None:
        raise RuntimeError('blob storage configuration is incomplete')
    return AzureBlobDocumentStorage(
        AzureBlobStorageConfig(
            connection_string=connection_string.get_secret_value(),
            container=settings.blob_container,
            api_version=settings.blob_api_version,
            connect_timeout=settings.blob_connect_timeout_seconds,
            read_timeout=settings.blob_read_timeout_seconds,
            operation_timeout=settings.blob_operation_timeout_seconds,
            retry_total=settings.blob_retry_total,
            block_size=settings.blob_block_size_bytes,
        )
    )
