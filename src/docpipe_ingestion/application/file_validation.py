import hashlib
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import PurePosixPath

from docpipe_ingestion.application.errors import (
    EmptyFileError,
    FileTooLargeError,
    InvalidFileMetadataError,
    UnsupportedFileTypeError,
)
from docpipe_ingestion.application.ports import BinarySource

_MAX_ORIGINAL_NAME_LENGTH = 255


@dataclass(frozen=True, slots=True)
class SupportedFileType:
    media_type: str
    extensions: frozenset[str]
    signature: bytes


@dataclass(frozen=True, slots=True)
class FileMetadata:
    media_type: str
    size_bytes: int
    sha256: str


_SUPPORTED_FILE_TYPES = (
    SupportedFileType(
        media_type='application/pdf',
        extensions=frozenset({'.pdf'}),
        signature=b'%PDF-',
    ),
    SupportedFileType(
        media_type='image/png',
        extensions=frozenset({'.png'}),
        signature=b'\x89PNG\r\n\x1a\n',
    ),
    SupportedFileType(
        media_type='image/jpeg',
        extensions=frozenset({'.jpg', '.jpeg'}),
        signature=b'\xff\xd8\xff',
    ),
)
_MAX_SIGNATURE_LENGTH = max(
    len(file_type.signature) for file_type in _SUPPORTED_FILE_TYPES
)


def sanitize_original_name(original_name: str) -> str:
    """Normalize a client filename for display-only metadata."""
    normalized = unicodedata.normalize('NFC', original_name).replace(
        '\\',
        '/',
    )
    name = PurePosixPath(normalized).name.strip()
    if not name or name in {'.', '..'}:
        raise InvalidFileMetadataError('original filename is empty')
    if len(name) > _MAX_ORIGINAL_NAME_LENGTH:
        raise InvalidFileMetadataError('original filename is too long')
    contains_control_character = any(
        unicodedata.category(character).startswith('C') for character in name
    )
    if contains_control_character:
        raise InvalidFileMetadataError(
            'original filename contains control characters'
        )
    return name


def _detect_file_type(header: bytes) -> SupportedFileType:
    for file_type in _SUPPORTED_FILE_TYPES:
        if header.startswith(file_type.signature):
            return file_type
    raise UnsupportedFileTypeError('file signature is not supported')


def _normalize_content_type(content_type: str) -> str:
    return content_type.partition(';')[0].strip().lower()


class ValidatedFileStream:
    """Validate, count, and hash a source while yielding bounded chunks."""

    def __init__(
        self,
        source: BinarySource,
        *,
        original_name: str,
        content_type: str,
        max_size_bytes: int,
        chunk_size_bytes: int,
    ) -> None:
        if max_size_bytes <= 0:
            raise ValueError('max_size_bytes must be positive')
        if chunk_size_bytes < _MAX_SIGNATURE_LENGTH:
            raise ValueError(
                'chunk_size_bytes must fit the longest supported signature'
            )
        self._source = source
        self._extension = PurePosixPath(original_name).suffix.lower()
        self._content_type = _normalize_content_type(content_type)
        self._max_size_bytes = max_size_bytes
        self._chunk_size_bytes = chunk_size_bytes
        self._started = False
        self._metadata: FileMetadata | None = None

    @property
    def metadata(self) -> FileMetadata:
        """Return metadata only after the stream was fully consumed."""
        if self._metadata is None:
            raise RuntimeError('file stream has not been consumed completely')
        return self._metadata

    def __iter__(self) -> Iterator[bytes]:
        if self._started:
            raise RuntimeError('file stream can only be consumed once')
        self._started = True
        return self._iterate()

    def _iterate(self) -> Iterator[bytes]:
        header = bytearray()
        while len(header) < _MAX_SIGNATURE_LENGTH:
            requested = _MAX_SIGNATURE_LENGTH - len(header)
            chunk = self._source.read(requested)
            if not chunk:
                break
            header.extend(chunk)
        if not header:
            raise EmptyFileError('file cannot be empty')
        if len(header) > self._max_size_bytes:
            raise FileTooLargeError(self._max_size_bytes)

        file_type = _detect_file_type(bytes(header))
        if self._extension not in file_type.extensions:
            raise UnsupportedFileTypeError(
                'filename extension does not match the detected type'
            )
        if self._content_type != file_type.media_type:
            raise UnsupportedFileTypeError(
                'content type does not match the detected type'
            )

        digest = hashlib.sha256()
        size_bytes = 0

        def account(chunk: bytes) -> bytes:
            nonlocal size_bytes
            size_bytes += len(chunk)
            if size_bytes > self._max_size_bytes:
                raise FileTooLargeError(self._max_size_bytes)
            digest.update(chunk)
            return chunk

        yield account(bytes(header))
        while True:
            chunk = self._source.read(self._chunk_size_bytes)
            if not chunk:
                break
            yield account(chunk)

        self._metadata = FileMetadata(
            media_type=file_type.media_type,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
        )
