"""Split a PDF into several files."""

from __future__ import annotations

import os

from .common import PdfWriter, ensure_dir, read_pdf, write_pdf
from .errors import PdfToolkitError
from .pages_util import parse_pages, to_zero_based


def _stem(path, prefix):
    if prefix:
        return prefix
    return os.path.splitext(os.path.basename(path))[0]


def split_pages(input, out_dir, prefix=None):
    """Write one file per page.

    Files are named ``<prefix>_page_<n>.pdf`` (1-based ``n``).

    :returns: list of output paths in page order.
    """
    reader = read_pdf(input)
    total = len(reader.pages)
    if total == 0:
        raise PdfToolkitError("cannot split a document with no pages")
    ensure_dir(out_dir)
    stem = _stem(input, prefix)

    outputs = []
    for i in range(total):
        writer = PdfWriter()
        writer.add_page(reader.pages[i])
        out = os.path.join(out_dir, f"{stem}_page_{i + 1}.pdf")
        write_pdf(writer, out)
        outputs.append(out)
    return outputs


def split_ranges(input, ranges, out_dir):
    """Write one file per range spec.

    *ranges* is a list of range strings, e.g. ``["1-3", "4-6", "7"]``.
    Output ``<stem>_<idx>.pdf`` preserves the requested page order.

    :returns: list of output paths.
    """
    if not ranges:
        raise PdfToolkitError("split_ranges requires at least one range")
    reader = read_pdf(input)
    total = len(reader.pages)
    ensure_dir(out_dir)
    stem = _stem(input, None)

    outputs = []
    for idx, spec in enumerate(ranges, start=1):
        pages = parse_pages(spec, total)
        writer = PdfWriter()
        for i in to_zero_based(pages):
            writer.add_page(reader.pages[i])
        out = os.path.join(out_dir, f"{stem}_{idx}.pdf")
        write_pdf(writer, out)
        outputs.append(out)
    return outputs


def split_every(input, n, out_dir):
    """Split into chunks of *n* consecutive pages.

    :returns: list of output paths.
    """
    if n < 1:
        raise PdfToolkitError("split_every requires n >= 1")
    reader = read_pdf(input)
    total = len(reader.pages)
    if total == 0:
        raise PdfToolkitError("cannot split a document with no pages")
    ensure_dir(out_dir)
    stem = _stem(input, None)

    outputs = []
    chunk = 0
    for start in range(0, total, n):
        chunk += 1
        writer = PdfWriter()
        for i in range(start, min(start + n, total)):
            writer.add_page(reader.pages[i])
        out = os.path.join(out_dir, f"{stem}_part_{chunk}.pdf")
        write_pdf(writer, out)
        outputs.append(out)
    return outputs
