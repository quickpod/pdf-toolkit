"""Merge multiple PDFs into one."""

from __future__ import annotations

from .common import PdfWriter, read_pdf, write_pdf
from .errors import PdfToolkitError


def merge(inputs, output):
    """Concatenate *inputs* (a list of paths) into a single PDF at *output*.

    :returns: total page count of the merged document.
    :raises PdfToolkitError: if *inputs* is empty or a file cannot be read.
    """
    if not inputs:
        raise PdfToolkitError("merge requires at least one input file")

    writer = PdfWriter()
    total = 0
    for inp in inputs:
        reader = read_pdf(inp)
        for page in reader.pages:
            writer.add_page(page)
            total += 1
    write_pdf(writer, output)
    return total
