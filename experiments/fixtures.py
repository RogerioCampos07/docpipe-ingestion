"""Small, deterministic documents with no personal information."""

import base64
import hashlib
import struct
import zlib
from dataclasses import dataclass

_JPEG = (
    '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEP'
    'ERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4e'
    'Hh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAACAAIDASIA'
    'AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA'
    'AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3'
    'ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm'
    'p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA'
    'AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSEx'
    'BhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElK'
    'U1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3'
    'uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDHooor'
    '6s+aP//Z'
)


@dataclass(frozen=True)
class Fixture:
    name: str
    media_type: str
    data: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def _pdf(label: str) -> bytes:
    stream = f'BT /F1 12 Tf 20 50 Td ({label}) Tj ET'.encode()
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] '
        b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length '
        + str(len(stream)).encode()
        + b' >>\nstream\n'
        + stream
        + b'\nendstream',
    ]
    output = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f'{number} 0 obj\n'.encode() + body + b'\nendobj\n')
    xref = len(output)
    output.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        output.extend(f'{offset:010d} 00000 n \n'.encode())
    output.extend(
        f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n'
        f'startxref\n{xref}\n%%EOF\n'.encode()
    )
    return bytes(output)


def _chunk(name: bytes, payload: bytes) -> bytes:
    return (
        struct.pack('>I', len(payload))
        + name
        + payload
        + struct.pack('>I', zlib.crc32(name + payload))
    )


def _png(rgb: tuple[int, int, int]) -> bytes:
    header = struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0)
    scanline = b'\0' + bytes(rgb) * 2
    return (
        b'\x89PNG\r\n\x1a\n'
        + _chunk(b'IHDR', header)
        + _chunk(b'IDAT', zlib.compress(scanline * 2, level=9))
        + _chunk(b'IEND', b'')
    )


def fixtures() -> tuple[Fixture, ...]:
    jpeg = base64.b64decode(_JPEG, validate=True)
    return (
        Fixture('a.pdf', 'application/pdf', _pdf('DocPipe synthetic A')),
        Fixture('b.pdf', 'application/pdf', _pdf('DocPipe synthetic B')),
        Fixture('a.png', 'image/png', _png((80, 120, 160))),
        Fixture('b.png', 'image/png', _png((160, 120, 80))),
        Fixture('a.jpg', 'image/jpeg', jpeg),
        Fixture('b.jpg', 'image/jpeg', jpeg),
    )
