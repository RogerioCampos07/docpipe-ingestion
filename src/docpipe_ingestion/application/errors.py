class IngestionError(Exception):
    """Base class for expected ingestion failures."""


class InvalidFileMetadataError(IngestionError):
    """Raised when client-supplied file metadata is unsafe."""


class EmptyFileError(IngestionError):
    """Raised when the supplied file has no content."""


class FileTooLargeError(IngestionError):
    """Raised when the actual streamed size exceeds the configured limit."""

    def __init__(self, max_size_bytes: int) -> None:
        self.max_size_bytes = max_size_bytes
        super().__init__('file exceeds the configured size limit')


class UnsupportedFileTypeError(IngestionError):
    """Raised when extension, content type, and signature do not agree."""


class StorageError(IngestionError):
    """Base class for storage adapter failures."""


class MetadataPersistenceError(IngestionError):
    """Raised after storage succeeds but metadata persistence fails."""

    def __init__(self, storage_key: str) -> None:
        self.storage_key = storage_key
        super().__init__(
            'metadata persistence failed after the file was stored'
        )


class MetadataQueryError(IngestionError):
    """Raised when document metadata cannot be queried safely."""


class DocumentNotFoundError(IngestionError):
    """Raised when a document identifier has no persisted metadata."""
