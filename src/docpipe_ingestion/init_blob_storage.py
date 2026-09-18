"""Idempotently initialize the configured private blob container."""

from docpipe_ingestion.infrastructure.composition import (
    create_document_storage,
)
from docpipe_ingestion.infrastructure.settings import Settings


def main() -> None:
    settings = Settings()
    if settings.storage_backend != 'azurite':
        raise SystemExit('storage backend is not azurite')
    storage = create_document_storage(settings)
    close = getattr(storage, 'close', None)
    if close is not None:
        close()


if __name__ == '__main__':
    main()
