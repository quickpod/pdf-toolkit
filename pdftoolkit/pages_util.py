"""Page-range parsing and small page helpers.

The public API uses **1-based** page numbers everywhere.  Internally most
libraries want 0-based indices, so use :func:`to_zero_based` at the boundary.
"""

from __future__ import annotations

from .errors import PdfToolkitError


def parse_pages(spec, total):
    """Parse a page-range spec like ``"1-3,5,8-10"`` into a list of 1-based ints.

    Order is preserved as written (so ``"3,1"`` -> ``[3, 1]``) and duplicates
    are kept (``"1,1"`` -> ``[1, 1]``); callers that need a set can dedupe.
    Whitespace is ignored.  Ranges may be ascending or descending
    (``"3-1"`` -> ``[3, 2, 1]``).

    :param spec: the range string, e.g. ``"1-3,5"``.  ``None`` or ``""`` selects
        every page ``1..total``.
    :param total: total number of pages in the document (used for validation).
    :returns: list of 1-based page numbers.
    :raises PdfToolkitError: on malformed input or out-of-range values.
    """
    if total < 0:
        raise PdfToolkitError("total pages cannot be negative")
    if spec is None or str(spec).strip() == "":
        return list(range(1, total + 1))

    pages = []
    for chunk in str(spec).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk.lstrip("-"):
            # a range (guard against a leading minus being read as negative)
            parts = chunk.split("-")
            if len(parts) != 2 or parts[0].strip() == "" or parts[1].strip() == "":
                raise PdfToolkitError(f"invalid page range: {chunk!r}")
            try:
                start = int(parts[0])
                end = int(parts[1])
            except ValueError:
                raise PdfToolkitError(f"invalid page range: {chunk!r}")
            step = 1 if end >= start else -1
            for p in range(start, end + step, step):
                _check(p, total)
                pages.append(p)
        else:
            try:
                p = int(chunk)
            except ValueError:
                raise PdfToolkitError(f"invalid page number: {chunk!r}")
            _check(p, total)
            pages.append(p)

    if not pages:
        raise PdfToolkitError(f"page spec selected no pages: {spec!r}")
    return pages


def _check(p, total):
    if p < 1 or p > total:
        raise PdfToolkitError(f"page {p} out of range (document has {total} pages)")


def to_zero_based(pages):
    """Convert a list of 1-based page numbers to 0-based indices."""
    return [p - 1 for p in pages]


def unique_sorted(pages):
    """Return the sorted set of the given pages (order-independent operations)."""
    return sorted(set(pages))
