"""Outline / bookmark operations."""

from __future__ import annotations

from .common import PdfWriter, read_pdf, write_pdf
from .errors import PdfToolkitError


def add_bookmark(input, output, title, page, parent=None):
    """Add a single bookmark pointing at *page* (1-based).

    :param parent: an outline-item object previously returned by this function
        (to nest under it), or ``None`` for a top-level entry.
    :returns: the created outline-item object (pass as *parent* to nest).

    .. note:: This rewrites the file, so bookmarks added across multiple calls
        must be chained (read the previous output).  For building a whole tree
        in one pass, use :func:`generate_toc`.
    """
    reader = read_pdf(input)
    total = len(reader.pages)
    if page < 1 or page > total:
        raise PdfToolkitError(f"page {page} out of range (1..{total})")
    writer = PdfWriter()
    writer.append(reader)
    item = writer.add_outline_item(title, page - 1, parent=parent)
    write_pdf(writer, output)
    return item


def list_bookmarks(input):
    """Return a flat list of ``{title, page, level}`` for every bookmark.

    *page* is 1-based (or ``None`` if the destination can't be resolved).
    """
    reader = read_pdf(input)
    result = []

    def walk(items, level):
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
                continue
            page = None
            try:
                page = reader.get_destination_page_number(item) + 1
            except Exception:  # noqa: BLE001
                page = None
            result.append({"title": str(item.title), "page": page, "level": level})

    try:
        walk(reader.outline, 0)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"could not read bookmarks: {exc}") from exc
    return result


def generate_toc(input, output, entries):
    """Build a flat outline from *entries* in one pass.

    :param entries: list of ``(title, page)`` pairs (1-based pages).
    :returns: number of bookmarks added.
    """
    if not entries:
        raise PdfToolkitError("generate_toc requires at least one entry")
    reader = read_pdf(input)
    total = len(reader.pages)
    writer = PdfWriter()
    writer.append(reader)
    for title, page in entries:
        if page < 1 or page > total:
            raise PdfToolkitError(f"page {page} out of range (1..{total})")
        writer.add_outline_item(title, page - 1)
    write_pdf(writer, output)
    return len(entries)
