"""Page-level operations: extract, delete, rotate, reorder, duplicate."""

from __future__ import annotations

from .common import PdfWriter, read_pdf, write_pdf
from .errors import PdfToolkitError
from .pages_util import parse_pages, to_zero_based, unique_sorted


def extract(input, output, pages_spec):
    """Keep only the pages in *pages_spec* (order preserved).

    :returns: number of pages written.
    """
    reader = read_pdf(input)
    total = len(reader.pages)
    pages = parse_pages(pages_spec, total)
    writer = PdfWriter()
    for i in to_zero_based(pages):
        writer.add_page(reader.pages[i])
    write_pdf(writer, output)
    return len(pages)


def delete(input, output, pages_spec):
    """Remove the pages in *pages_spec*, keeping the rest in order.

    :returns: number of pages written.
    """
    reader = read_pdf(input)
    total = len(reader.pages)
    drop = set(parse_pages(pages_spec, total))
    keep = [p for p in range(1, total + 1) if p not in drop]
    if not keep:
        raise PdfToolkitError("delete would remove every page")
    writer = PdfWriter()
    for i in to_zero_based(keep):
        writer.add_page(reader.pages[i])
    write_pdf(writer, output)
    return len(keep)


def rotate(input, output, degrees, pages_spec=None):
    """Rotate pages by *degrees* (a multiple of 90; may be negative).

    *pages_spec* selects which pages to rotate; ``None`` rotates all pages.
    Rotation is cumulative with any existing page rotation.

    :returns: number of pages written (== total page count).
    """
    if degrees % 90 != 0:
        raise PdfToolkitError("rotation must be a multiple of 90 degrees")
    reader = read_pdf(input)
    total = len(reader.pages)
    sel = set(parse_pages(pages_spec, total)) if pages_spec else set(range(1, total + 1))

    writer = PdfWriter()
    for i, page in enumerate(reader.pages, start=1):
        if i in sel:
            page.rotate(degrees)
        writer.add_page(page)
    write_pdf(writer, output)
    return total


def reorder(input, output, order):
    """Rearrange pages according to *order* (a list of 1-based page numbers).

    *order* must be a permutation of ``1..total`` (each page exactly once).

    :returns: number of pages written.
    """
    reader = read_pdf(input)
    total = len(reader.pages)
    if unique_sorted(order) != list(range(1, total + 1)):
        raise PdfToolkitError(
            f"reorder needs a permutation of 1..{total}; got {order}"
        )
    writer = PdfWriter()
    for p in order:
        writer.add_page(reader.pages[p - 1])
    write_pdf(writer, output)
    return total


def duplicate(input, output, pages_spec):
    """Duplicate the pages in *pages_spec*.

    Each selected page is emitted twice, in place (the copy immediately
    follows the original); all other pages are emitted once.

    :returns: number of pages written.
    """
    reader = read_pdf(input)
    total = len(reader.pages)
    dup = set(parse_pages(pages_spec, total))
    writer = PdfWriter()
    written = 0
    for i, page in enumerate(reader.pages, start=1):
        writer.add_page(page)
        written += 1
        if i in dup:
            writer.add_page(reader.pages[i - 1])
            written += 1
    write_pdf(writer, output)
    return written
