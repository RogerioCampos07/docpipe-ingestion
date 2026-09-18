"""Private blob storage adapter validated locally against Azurite."""

import base64
import hashlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from azure.core.exceptions import AzureError, ResourceExistsError
from azure.storage.blob import BlobBlock, BlobServiceClient, ContentSettings

from docpipe_ingestion.application.errors import StorageError
from docpipe_ingestion.infrastructure.storage.keys import (
    STORAGE_KEY_PATTERN,
    validate_storage_key,
)
from docpipe_ingestion.infrastructure.storage.local import (
    StorageObjectExistsError,
    UnsafeStorageKeyError,
)

_UPLOAD_PREFIX = '_uploads/'
_HEADER_SIZE = 8


@dataclass(frozen=True, slots=True)
class AzureBlobStorageConfig:
    connection_string: str
    container: str
    api_version: str
    connect_timeout: float
    read_timeout: float
    operation_timeout: int
    retry_total: int
    block_size: int


@dataclass(slots=True)
class _UploadState:
    marker: Any
    blob: Any
    attempt: str
    digest: Any
    header: bytearray
    block_ids: list[BlobBlock]


class BlobStorageWriteError(StorageError):
    """Raised when the object service cannot complete an operation."""


class AzureBlobDocumentStorage:
    """Store documents through the Azure Blob API using private blobs."""

    def __init__(
        self,
        config: AzureBlobStorageConfig,
    ) -> None:
        self._service = BlobServiceClient.from_connection_string(
            config.connection_string,
            api_version=config.api_version,
            connection_timeout=config.connect_timeout,
            read_timeout=config.read_timeout,
            retry_total=config.retry_total,
        )
        self._container = self._service.get_container_client(config.container)
        self._operation_timeout = config.operation_timeout
        self._block_size = config.block_size

    def ensure_private_container(self) -> None:
        """Create the configured container without public access."""
        try:
            self._create_or_check_container()
        except BlobStorageWriteError:
            raise
        except AzureError as error:
            raise BlobStorageWriteError(
                'blob container is not available'
            ) from error

    def _create_or_check_container(self) -> None:
        try:
            self._container.create_container(
                public_access=None,
                timeout=self._operation_timeout,
            )
        except ResourceExistsError:
            properties = self._container.get_container_properties(
                timeout=self._operation_timeout
            )
            if properties.public_access is not None:
                raise BlobStorageWriteError(
                    'blob container must not allow public access'
                )

    @staticmethod
    def _media_type(header: bytes) -> str:
        if header.startswith(b'%PDF-'):
            return 'application/pdf'
        if header.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        if header.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        return 'application/octet-stream'

    def _blocks(self, chunks: Iterable[bytes]) -> Iterator[bytes]:
        buffer = bytearray()
        for chunk in chunks:
            buffer.extend(chunk)
            while len(buffer) >= self._block_size:
                yield bytes(buffer[: self._block_size])
                del buffer[: self._block_size]
        if buffer:
            yield bytes(buffer)

    def store(self, storage_key: str, chunks: Iterable[bytes]) -> None:
        try:
            validate_storage_key(storage_key)
        except ValueError as error:
            raise UnsafeStorageKeyError(str(error)) from error
        attempt = uuid4().hex
        marker_name = f'{_UPLOAD_PREFIX}{attempt}/{storage_key}'
        marker = self._container.get_blob_client(marker_name)
        blob = self._container.get_blob_client(storage_key)
        state = _UploadState(
            marker=marker,
            blob=blob,
            attempt=attempt,
            digest=hashlib.sha256(),
            header=bytearray(),
            block_ids=[],
        )
        try:
            self._perform_upload(state, chunks)
        except ResourceExistsError as error:
            raise StorageObjectExistsError(
                'storage key already exists and will not be overwritten'
            ) from error
        except StorageError:
            raise
        except AzureError as error:
            raise BlobStorageWriteError('blob storage write failed') from error

    def _perform_upload(
        self,
        state: _UploadState,
        chunks: Iterable[bytes],
    ) -> None:
        state.marker.upload_blob(
            b'',
            overwrite=False,
            metadata={'started_at': datetime.now(UTC).isoformat()},
            timeout=self._operation_timeout,
        )
        size = 0
        for index, block in enumerate(self._blocks(chunks)):
            state.digest.update(block)
            size += len(block)
            if len(state.header) < _HEADER_SIZE:
                state.header.extend(block[: _HEADER_SIZE - len(state.header)])
            block_id = base64.b64encode(
                f'{state.attempt}-{index:08d}'.encode()
            ).decode()
            state.blob.stage_block(
                block_id=block_id,
                data=block,
                length=len(block),
                timeout=self._operation_timeout,
            )
            state.block_ids.append(BlobBlock(block_id=block_id))
        state.blob.commit_block_list(
            state.block_ids,
            metadata={
                'sha256': state.digest.hexdigest(),
                'size': str(size),
                'owner': 'docpipe-ingestion',
            },
            content_settings=ContentSettings(
                content_type=self._media_type(bytes(state.header))
            ),
            if_none_match='*',
            timeout=self._operation_timeout,
        )
        state.marker.delete_blob(timeout=self._operation_timeout)

    def list_keys(self) -> set[str]:
        try:
            return {
                item.name
                for item in self._container.list_blobs(
                    timeout=self._operation_timeout
                )
                if STORAGE_KEY_PATTERN.fullmatch(item.name) is not None
            }
        except AzureError as error:
            raise BlobStorageWriteError(
                'blob storage listing failed'
            ) from error

    def list_incomplete(self, *, older_than: datetime) -> set[str]:
        if older_than.tzinfo is None or older_than.utcoffset() is None:
            raise ValueError('older_than must include timezone information')
        cutoff = older_than.astimezone(UTC)
        try:
            return {
                item.name
                for item in self._container.list_blobs(
                    name_starts_with=_UPLOAD_PREFIX,
                    timeout=self._operation_timeout,
                )
                if item.last_modified <= cutoff
            }
        except AzureError as error:
            raise BlobStorageWriteError(
                'blob storage listing failed'
            ) from error

    def close(self) -> None:
        self._service.close()
