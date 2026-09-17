import os
import stat
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from docpipe_ingestion.infrastructure.storage.local import (
    LocalDocumentStorage,
    StorageObjectExistsError,
    StorageWriteError,
    UnsafeStorageKeyError,
)

STORAGE_KEY = f'{"a" * 32}.blob'
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)
PRIVATE_FILE_MODE = 0o600


def test_local_storage_writes_private_file_atomically(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')

    storage.store(STORAGE_KEY, [b'first', b'-second'])

    destination = storage.root / STORAGE_KEY
    assert destination.read_bytes() == b'first-second'
    assert stat.S_IMODE(destination.stat().st_mode) == PRIVATE_FILE_MODE
    assert not list(storage.root.glob('*.part'))


@pytest.mark.parametrize(
    'storage_key',
    [
        '../outside.blob',
        '/tmp/outside.blob',
        f'{"a" * 31}.blob',
        f'{"a" * 32}/nested.blob',
    ],
)
def test_local_storage_rejects_unsafe_storage_key(
    tmp_path: Path,
    storage_key: str,
) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')

    with pytest.raises(UnsafeStorageKeyError):
        storage.store(storage_key, [b'content'])

    assert not (tmp_path / 'outside.blob').exists()


def test_local_storage_rejects_symlink_escape(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')
    outside = tmp_path / 'outside.blob'
    outside.write_bytes(b'outside')
    (storage.root / STORAGE_KEY).symlink_to(outside)

    with pytest.raises(UnsafeStorageKeyError, match='escapes'):
        storage.store(STORAGE_KEY, [b'content'])

    assert outside.read_bytes() == b'outside'


def test_local_storage_never_overwrites_existing_object(
    tmp_path: Path,
) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')
    storage.store(STORAGE_KEY, [b'original'])

    with pytest.raises(StorageObjectExistsError):
        storage.store(STORAGE_KEY, [b'replacement'])

    assert (storage.root / STORAGE_KEY).read_bytes() == b'original'


def test_local_storage_removes_temporary_file_when_stream_fails(
    tmp_path: Path,
) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')

    def failing_chunks() -> Iterator[bytes]:
        yield b'partial'
        raise RuntimeError('synthetic read failure')

    with pytest.raises(RuntimeError, match='synthetic read failure'):
        storage.store(STORAGE_KEY, failing_chunks())

    assert not (storage.root / STORAGE_KEY).exists()
    assert not list(storage.root.glob('*.part'))


def test_local_storage_removes_temporary_file_when_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')

    def fail_fsync(file_descriptor: int) -> None:
        del file_descriptor
        raise OSError('synthetic disk failure')

    monkeypatch.setattr(os, 'fsync', fail_fsync)

    with pytest.raises(StorageWriteError):
        storage.store(STORAGE_KEY, [b'content'])

    assert not (storage.root / STORAGE_KEY).exists()
    assert not list(storage.root.glob('*.part'))


def test_local_storage_lists_only_old_incomplete_files(
    tmp_path: Path,
) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')
    old_file = storage.root / '.upload-old.part'
    recent_file = storage.root / '.upload-recent.part'
    old_file.write_bytes(b'partial')
    recent_file.write_bytes(b'partial')
    old_time = (NOW - timedelta(hours=2)).timestamp()
    recent_time = NOW.timestamp()
    os.utime(old_file, (old_time, old_time))
    os.utime(recent_file, (recent_time, recent_time))

    incomplete = storage.list_incomplete(older_than=NOW - timedelta(hours=1))

    assert incomplete == {old_file.name}
    assert old_file.exists()
    assert recent_file.exists()


def test_local_storage_requires_aware_incomplete_cutoff(
    tmp_path: Path,
) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')

    with pytest.raises(ValueError, match='timezone'):
        storage.list_incomplete(older_than=datetime(2026, 9, 17))


def test_local_storage_reports_unavailable_root(tmp_path: Path) -> None:
    root_file = tmp_path / 'not-a-directory'
    root_file.write_bytes(b'content')

    with pytest.raises(StorageWriteError, match='root'):
        LocalDocumentStorage(root_file)


def test_local_storage_reports_listing_failures(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')
    storage.root.rmdir()

    with pytest.raises(StorageWriteError, match='listing'):
        storage.list_keys()
    with pytest.raises(StorageWriteError, match='listing'):
        storage.list_incomplete(older_than=NOW)
