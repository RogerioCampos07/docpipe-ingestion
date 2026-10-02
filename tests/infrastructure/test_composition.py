from pathlib import Path
from unittest.mock import Mock

import pytest

from docpipe_ingestion.infrastructure import composition
from docpipe_ingestion.infrastructure.composition import (
    create_azure_blob_storage,
    create_document_storage,
)
from docpipe_ingestion.infrastructure.settings import Settings
from docpipe_ingestion.infrastructure.storage.local import LocalDocumentStorage


def test_composition_selects_local_storage_without_remote_configuration(
    tmp_path: Path,
) -> None:
    storage = create_document_storage(
        Settings(
            environment='test',
            storage_backend='local',
            storage_root=tmp_path / 'documents',
        )
    )

    assert isinstance(storage, LocalDocumentStorage)


def test_azure_storage_adapter_can_be_constructed_without_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = Mock()
    monkeypatch.setattr(
        composition,
        'AzureBlobDocumentStorage',
        Mock(return_value=storage),
    )

    result = create_azure_blob_storage(Settings())

    assert result is storage
    storage.ensure_private_container.assert_not_called()
