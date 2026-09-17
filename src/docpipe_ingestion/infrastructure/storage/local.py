import os
import re
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from docpipe_ingestion.application.errors import StorageError

_STORAGE_KEY_PATTERN = re.compile(r'[0-9a-f]{32}\.blob')
_INCOMPLETE_PATTERN = re.compile(r'\.upload-[0-9a-z_-]+\.part')


class UnsafeStorageKeyError(StorageError):
    """Raised when a storage key is not an opaque service key."""


class StorageObjectExistsError(StorageError):
    """Raised rather than overwriting an existing stored document."""


class StorageWriteError(StorageError):
    """Raised when the local filesystem cannot complete an operation."""


class LocalDocumentStorage:
    """Store private documents below one resolved local root."""

    def __init__(self, root: Path) -> None:
        configured_root = root.expanduser()
        try:
            configured_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            resolved_root = configured_root.resolve(strict=True)
        except OSError as error:
            raise StorageWriteError(
                'local storage root is not available'
            ) from error
        if not resolved_root.is_dir():
            raise StorageWriteError('local storage root is not a directory')
        self._root = resolved_root

    @property
    def root(self) -> Path:
        return self._root

    def _destination(self, storage_key: str) -> Path:
        if _STORAGE_KEY_PATTERN.fullmatch(storage_key) is None:
            raise UnsafeStorageKeyError('storage key is not valid')
        destination = (self._root / storage_key).resolve(strict=False)
        if not destination.is_relative_to(self._root):
            raise UnsafeStorageKeyError('storage key escapes the storage root')
        return destination

    @staticmethod
    def _ensure_destination_is_available(destination: Path) -> None:
        if destination.exists():
            raise StorageObjectExistsError(
                'storage key already exists and will not be overwritten'
            )

    def _write_temporary(self, chunks: Iterable[bytes]) -> Path:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self._root,
            prefix='.upload-',
            suffix='.part',
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, 'wb') as temporary_file:
                for chunk in chunks:
                    temporary_file.write(chunk)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
        return temporary_path

    def store(self, storage_key: str, chunks: Iterable[bytes]) -> None:
        """Write a temporary file and atomically publish it."""
        destination = self._destination(storage_key)
        temporary_path: Path | None = None
        try:
            self._ensure_destination_is_available(destination)
            temporary_path = self._write_temporary(chunks)
            self._ensure_destination_is_available(destination)
            os.replace(temporary_path, destination)
            temporary_path = None
        except StorageError:
            raise
        except OSError as error:
            raise StorageWriteError('local storage write failed') from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def list_keys(self) -> set[str]:
        """List complete service-owned objects without following symlinks."""
        try:
            return {
                path.name
                for path in self._root.iterdir()
                if not path.is_symlink()
                and path.is_file()
                and _STORAGE_KEY_PATTERN.fullmatch(path.name) is not None
            }
        except OSError as error:
            raise StorageWriteError('local storage listing failed') from error

    def list_incomplete(self, *, older_than: datetime) -> set[str]:
        """List old temporary files without modifying them."""
        if older_than.tzinfo is None or older_than.utcoffset() is None:
            raise ValueError('older_than must include timezone information')
        cutoff = older_than.astimezone(UTC)
        try:
            return {
                path.name
                for path in self._root.iterdir()
                if not path.is_symlink()
                and path.is_file()
                and _INCOMPLETE_PATTERN.fullmatch(path.name) is not None
                and datetime.fromtimestamp(path.stat().st_mtime, UTC) <= cutoff
            }
        except OSError as error:
            raise StorageWriteError('local storage listing failed') from error
