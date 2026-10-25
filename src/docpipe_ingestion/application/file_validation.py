import hashlib
import tempfile
import unicodedata
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from io import SEEK_END
from pathlib import PurePosixPath
from types import TracebackType
from typing import IO, Self

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import DictionaryObject

from docpipe_ingestion.application.errors import (
    EmptyFileError,
    FileTooLargeError,
    InvalidFileMetadataError,
    InvalidFileStructureError,
    UnsupportedFileTypeError,
)
from docpipe_ingestion.application.ports import BinarySource

_MAX_ORIGINAL_NAME_LENGTH = 255
_SPOOL_MEMORY_LIMIT_BYTES = 1024 * 1024
_PDF_TRAILER_SCAN_BYTES = 1024
MAX_IMAGE_PIXELS = 40_000_000


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
    """Stage, structurally validate, and replay one bounded file stream."""

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
        self._temporary: IO[bytes] | None = None
        self._iterated = False
        self._metadata: FileMetadata | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback
        self.close()

    def close(self) -> None:
        """Release the staged upload, whether it is in memory or on disk."""
        if self._temporary is not None:
            self._temporary.close()
            self._temporary = None

    def validate(self) -> None:
        """Consume and validate the source before definitive storage."""
        if self._temporary is not None:
            raise RuntimeError('file stream has already been validated')
        temporary = tempfile.SpooledTemporaryFile(
            max_size=min(
                _SPOOL_MEMORY_LIMIT_BYTES,
                self._max_size_bytes,
            ),
            mode='w+b',
        )
        self._temporary = temporary
        try:
            self._stage_and_validate(temporary)
        except BaseException:
            self.close()
            raise

    @property
    def metadata(self) -> FileMetadata:
        """Return metadata only after the stream was fully consumed."""
        if self._metadata is None:
            raise RuntimeError('file stream has not been consumed completely')
        return self._metadata

    def __iter__(self) -> Iterator[bytes]:
        if self._temporary is None or self._metadata is None:
            raise RuntimeError('file stream has not been validated')
        if self._iterated:
            raise RuntimeError('file stream can only be consumed once')
        self._iterated = True
        self._temporary.seek(0)
        return self._replay(self._temporary)

    def _stage_and_validate(self, temporary: IO[bytes]) -> None:
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

        def account(chunk: bytes) -> None:
            nonlocal size_bytes
            size_bytes += len(chunk)
            if size_bytes > self._max_size_bytes:
                raise FileTooLargeError(self._max_size_bytes)
            digest.update(chunk)
            temporary.write(chunk)

        account(bytes(header))
        while True:
            chunk = self._source.read(self._chunk_size_bytes)
            if not chunk:
                break
            account(chunk)

        self._metadata = FileMetadata(
            media_type=file_type.media_type,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
        )
        temporary.seek(0)
        _validate_structure(temporary, file_type.media_type)

    def _replay(self, temporary: IO[bytes]) -> Iterator[bytes]:
        while chunk := temporary.read(self._chunk_size_bytes):
            yield chunk


def _validate_structure(source: IO[bytes], media_type: str) -> None:
    if media_type == 'application/pdf':
        _validate_pdf(source)
    else:
        _validate_image(source, media_type)
    source.seek(0)


def _validate_pdf(source: IO[bytes]) -> None:
    source.seek(0, SEEK_END)
    size = source.tell()
    source.seek(max(0, size - _PDF_TRAILER_SCAN_BYTES))
    if b'%%EOF' not in source.read():
        raise InvalidFileStructureError('PDF end-of-file marker is missing')
    source.seek(0)
    try:
        _parse_pdf_structure(source)
    except InvalidFileStructureError:
        raise
    except (PdfReadError, OSError, TypeError, ValueError) as error:
        raise InvalidFileStructureError('PDF structure is invalid') from error


def _parse_pdf_structure(source: IO[bytes]) -> None:
    reader = PdfReader(source, strict=False)
    if reader.trailer.get('/Root') is None:
        raise InvalidFileStructureError('PDF document catalog is missing')
    if reader.is_encrypted:
        return
    root = reader.trailer['/Root'].get_object()
    if not isinstance(root, DictionaryObject):
        raise InvalidFileStructureError('PDF document catalog is invalid')
    pages = root.get('/Pages')
    if pages is None:
        raise InvalidFileStructureError('PDF page tree is missing')
    pages.get_object()
    len(reader.pages)


def _validate_image(source: IO[bytes], media_type: str) -> None:
    expected_format = 'PNG' if media_type == 'image/png' else 'JPEG'
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            _decode_image(source, expected_format)
    except InvalidFileStructureError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        SyntaxError,
        UnidentifiedImageError,
        ValueError,
    ) as error:
        raise InvalidFileStructureError(
            'image structure is invalid'
        ) from error


def _decode_image(source: IO[bytes], expected_format: str) -> None:
    with Image.open(source) as image:
        if image.format != expected_format:
            raise InvalidFileStructureError(
                'image format does not match the detected type'
            )
        width, height = image.size
        if width * height > MAX_IMAGE_PIXELS:
            raise InvalidFileStructureError(
                'image exceeds the decoded pixel limit'
            )
        image.verify()
    source.seek(0)
    with Image.open(source) as image:
        image.load()
