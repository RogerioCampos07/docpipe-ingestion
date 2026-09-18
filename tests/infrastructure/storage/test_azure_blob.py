from typing import Any

import pytest

from docpipe_ingestion.infrastructure.storage.azure_blob import (
    AzureBlobDocumentStorage,
    AzureBlobStorageConfig,
)
from docpipe_ingestion.infrastructure.storage.local import (
    UnsafeStorageKeyError,
)


class FakeBlob:
    def __init__(self) -> None:
        self.blocks: list[bytes] = []
        self.committed: list[Any] = []
        self.deleted = False

    @staticmethod
    def upload_blob(data: bytes, **kwargs: object) -> None:
        del data, kwargs

    def stage_block(
        self, *, block_id: str, data: bytes, length: int, **kwargs: object
    ) -> None:
        del block_id, kwargs
        assert length == len(data)
        self.blocks.append(data)

    def commit_block_list(self, blocks: list[Any], **kwargs: object) -> None:
        del kwargs
        self.committed = blocks

    def delete_blob(self, **kwargs: object) -> None:
        del kwargs
        self.deleted = True


class FakeContainer:
    def __init__(self) -> None:
        self.blobs: dict[str, FakeBlob] = {}

    def get_blob_client(self, name: str) -> FakeBlob:
        return self.blobs.setdefault(name, FakeBlob())


class FakeService:
    def __init__(self) -> None:
        self.container = FakeContainer()

    def get_container_client(self, name: str) -> FakeContainer:
        del name
        return self.container

    def close(self) -> None:
        pass


def _storage(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[AzureBlobDocumentStorage, FakeService]:
    service = FakeService()
    monkeypatch.setattr(
        'docpipe_ingestion.infrastructure.storage.azure_blob.'
        'BlobServiceClient.from_connection_string',
        lambda *args, **kwargs: service,
    )
    storage = AzureBlobDocumentStorage(
        AzureBlobStorageConfig(
            connection_string='private',
            container='documents',
            api_version='2023-11-03',
            connect_timeout=1,
            read_timeout=1,
            operation_timeout=1,
            retry_total=0,
            block_size=64 * 1024,
        )
    )
    return storage, service


def test_blob_adapter_streams_bounded_blocks_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage, service = _storage(monkeypatch)
    key = f'{"a" * 32}.blob'
    content = b'%PDF-' + (b'a' * 150_000)

    storage.store(
        key,
        (
            content[index : index + 1000]
            for index in range(0, len(content), 1000)
        ),
    )

    blob = service.container.blobs[key]
    assert b''.join(blob.blocks) == content
    assert max(map(len, blob.blocks)) <= 64 * 1024
    assert blob.committed


def test_blob_adapter_rejects_unsafe_key_before_remote_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage, service = _storage(monkeypatch)

    with pytest.raises(UnsafeStorageKeyError):
        storage.store('../private.blob', [b'content'])

    assert service.container.blobs == {}
