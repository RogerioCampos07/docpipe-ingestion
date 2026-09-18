from pathlib import Path

from docpipe_ingestion.infrastructure.composition import (
    create_document_storage,
)
from docpipe_ingestion.infrastructure.settings import Settings
from docpipe_ingestion.infrastructure.storage.local import LocalDocumentStorage


def test_composition_selects_local_storage_without_remote_configuration(
    tmp_path: Path,
) -> None:
    storage = create_document_storage(
        Settings(storage_backend='local', storage_root=tmp_path / 'documents')
    )

    assert isinstance(storage, LocalDocumentStorage)
