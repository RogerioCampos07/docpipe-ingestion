import hashlib
from io import BytesIO

import pytest

from docpipe_ingestion.application.errors import (
    EmptyFileError,
    FileTooLargeError,
    InvalidFileMetadataError,
    InvalidFileStructureError,
    UnsupportedFileTypeError,
)
from docpipe_ingestion.application.file_validation import (
    ValidatedFileStream,
    sanitize_original_name,
)
from tests.document_fixtures import (
    valid_jpeg,
    valid_pdf,
    valid_png,
)

CHUNK_SIZE_BYTES = 8
FALSE_PDF = b'%PDF-1.7\nDocumento sint\xc3\xa9tico para teste local.\n'


def _consume(stream: ValidatedFileStream) -> bytes:
    with stream:
        stream.validate()
        return b''.join(stream)


class SpySource:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self._position = 0
        self.requested_sizes: list[int] = []

    def read(self, size: int, /) -> bytes:
        self.requested_sizes.append(size)
        start = self._position
        self._position += size
        return self._content[start : self._position]


@pytest.mark.parametrize(
    ('filename', 'content_type', 'content', 'detected_type'),
    [
        (
            'sample.pdf',
            'application/pdf',
            valid_pdf(),
            'application/pdf',
        ),
        (
            'sample.png',
            'image/png',
            valid_png(),
            'image/png',
        ),
        (
            'sample.jpg',
            'image/jpeg',
            valid_jpeg(),
            'image/jpeg',
        ),
        (
            'sample.jpeg',
            'image/jpeg',
            valid_jpeg(),
            'image/jpeg',
        ),
    ],
)
def test_validated_stream_accepts_supported_signatures(
    filename: str,
    content_type: str,
    content: bytes,
    detected_type: str,
) -> None:
    stream = ValidatedFileStream(
        BytesIO(content),
        original_name=filename,
        content_type=content_type,
        max_size_bytes=len(content),
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )

    stored_content = _consume(stream)

    assert stored_content == content
    assert stream.metadata.media_type == detected_type
    assert stream.metadata.size_bytes == len(content)
    assert stream.metadata.sha256 == hashlib.sha256(content).hexdigest()


def test_validated_stream_uses_only_bounded_reads() -> None:
    content = valid_pdf()
    source = SpySource(content)
    stream = ValidatedFileStream(
        source,
        original_name='sample.pdf',
        content_type='application/pdf',
        max_size_bytes=len(content),
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )

    assert _consume(stream) == content
    assert source.requested_sizes
    assert max(source.requested_sizes) <= CHUNK_SIZE_BYTES


def test_validated_stream_accepts_exact_size_limit() -> None:
    content = valid_pdf()
    stream = ValidatedFileStream(
        BytesIO(content),
        original_name='sample.pdf',
        content_type='application/pdf',
        max_size_bytes=len(content),
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )

    assert _consume(stream) == content


def test_validated_stream_rejects_first_byte_above_limit() -> None:
    content = b'%PDF-1234'
    stream = ValidatedFileStream(
        BytesIO(content),
        original_name='sample.pdf',
        content_type='application/pdf',
        max_size_bytes=len(content) - 1,
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )

    with pytest.raises(FileTooLargeError):
        stream.validate()


def test_validated_stream_rejects_empty_file() -> None:
    stream = ValidatedFileStream(
        BytesIO(),
        original_name='sample.pdf',
        content_type='application/pdf',
        max_size_bytes=100,
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )

    with pytest.raises(EmptyFileError):
        stream.validate()


def test_validated_stream_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match='max_size_bytes'):
        ValidatedFileStream(
            BytesIO(b'%PDF-1.7'),
            original_name='sample.pdf',
            content_type='application/pdf',
            max_size_bytes=0,
            chunk_size_bytes=CHUNK_SIZE_BYTES,
        )

    with pytest.raises(ValueError, match='chunk_size_bytes'):
        ValidatedFileStream(
            BytesIO(b'%PDF-1.7'),
            original_name='sample.pdf',
            content_type='application/pdf',
            max_size_bytes=100,
            chunk_size_bytes=1,
        )


def test_metadata_is_available_only_after_validation() -> None:
    content = valid_pdf()
    stream = ValidatedFileStream(
        BytesIO(content),
        original_name='sample.pdf',
        content_type='application/pdf',
        max_size_bytes=len(content),
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )

    with pytest.raises(RuntimeError, match='not been consumed'):
        _ = stream.metadata
    with stream:
        stream.validate()
        assert stream.metadata.size_bytes == len(content)
        b''.join(stream)
        with pytest.raises(RuntimeError, match='only be consumed once'):
            b''.join(stream)


def test_validated_stream_rejects_when_header_already_exceeds_limit() -> None:
    stream = ValidatedFileStream(
        BytesIO(b'%PDF-1.7'),
        original_name='sample.pdf',
        content_type='application/pdf',
        max_size_bytes=7,
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )

    with pytest.raises(FileTooLargeError):
        stream.validate()


@pytest.mark.parametrize(
    ('filename', 'content_type', 'content'),
    [
        ('sample.txt', 'text/plain', b'plain text'),
        ('sample.png', 'image/png', b'%PDF-1.7'),
        ('sample.pdf', 'image/png', b'%PDF-1.7'),
        ('sample.pdf', 'application/pdf', b'%PD'),
    ],
)
def test_validated_stream_rejects_unsupported_or_mismatched_type(
    filename: str,
    content_type: str,
    content: bytes,
) -> None:
    stream = ValidatedFileStream(
        BytesIO(content),
        original_name=filename,
        content_type=content_type,
        max_size_bytes=100,
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )

    with pytest.raises(UnsupportedFileTypeError):
        stream.validate()


@pytest.mark.parametrize(
    ('filename', 'content_type', 'content'),
    [
        ('false.pdf', 'application/pdf', FALSE_PDF),
        ('truncated.pdf', 'application/pdf', valid_pdf()[:-20]),
        (
            'corrupt.pdf',
            'application/pdf',
            valid_pdf().replace(b'/Root', b'/R00t'),
        ),
        ('truncated.png', 'image/png', valid_png()[:-8]),
        ('corrupt.png', 'image/png', valid_png()[:-12] + b'corruption!!'),
        ('truncated.jpg', 'image/jpeg', valid_jpeg()[:-10]),
        ('corrupt.jpg', 'image/jpeg', valid_jpeg()[:40] + b'broken-data'),
    ],
)
def test_validated_stream_rejects_invalid_structure(
    filename: str,
    content_type: str,
    content: bytes,
) -> None:
    stream = ValidatedFileStream(
        BytesIO(content),
        original_name=filename,
        content_type=content_type,
        max_size_bytes=len(content),
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )

    with pytest.raises(InvalidFileStructureError):
        stream.validate()
    assert stream._temporary is None


def test_validated_stream_preserves_encrypted_pdf_policy() -> None:
    content = valid_pdf(encrypted=True)
    stream = ValidatedFileStream(
        BytesIO(content),
        original_name='encrypted.pdf',
        content_type='application/pdf',
        max_size_bytes=len(content),
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )

    assert _consume(stream) == content


def test_sanitize_original_name_removes_client_paths() -> None:
    assert sanitize_original_name('../../sample.pdf') == 'sample.pdf'
    assert sanitize_original_name(r'C:\fakepath\sample.pdf') == 'sample.pdf'


@pytest.mark.parametrize('filename', ['', '..', 'sample\x00.pdf'])
def test_sanitize_original_name_rejects_invalid_name(filename: str) -> None:
    with pytest.raises(InvalidFileMetadataError):
        sanitize_original_name(filename)


def test_sanitize_original_name_rejects_excessive_length() -> None:
    filename = f'{"a" * 252}.pdf'

    with pytest.raises(InvalidFileMetadataError, match='too long'):
        sanitize_original_name(filename)
