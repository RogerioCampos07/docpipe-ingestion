from functools import cache
from io import BytesIO

from PIL import Image
from pypdf import PdfWriter


@cache
def valid_pdf(*, encrypted: bool = False) -> bytes:
    """Return a small synthetic PDF with a catalog, page tree, xref and EOF."""
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt('synthetic-password')
    writer.write(output)
    return output.getvalue()


@cache
def valid_png() -> bytes:
    return _image('PNG')


@cache
def valid_jpeg() -> bytes:
    return _image('JPEG')


def _image(image_format: str) -> bytes:
    output = BytesIO()
    with Image.new('RGB', (2, 2), color=(24, 96, 160)) as image:
        image.save(output, format=image_format)
    return output.getvalue()
