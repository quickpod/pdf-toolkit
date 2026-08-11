"""Per-page text diff between two PDFs."""

from __future__ import annotations

import difflib

from .common import read_pdf


def _page_lines(reader, index):
    try:
        text = reader.pages[index].extract_text() or ""
    except Exception:  # noqa: BLE001
        text = ""
    return text.splitlines()


def compare_text(a, b):
    """Diff the extracted text of *a* and *b*, page by page.

    Pages are compared positionally (page 1 vs page 1, ...).  If the documents
    differ in length, the shorter is padded with empty pages.

    :returns: dict with ``pages`` (list of per-page
        ``{page, added, removed, changed}``), ``total_added``,
        ``total_removed`` and ``identical`` (bool).
    """
    ra = read_pdf(a)
    rb = read_pdf(b)
    n = max(len(ra.pages), len(rb.pages))

    pages = []
    total_added = 0
    total_removed = 0
    for i in range(n):
        la = _page_lines(ra, i) if i < len(ra.pages) else []
        lb = _page_lines(rb, i) if i < len(rb.pages) else []
        added = removed = 0
        for line in difflib.ndiff(la, lb):
            if line.startswith("+ "):
                added += 1
            elif line.startswith("- "):
                removed += 1
        total_added += added
        total_removed += removed
        pages.append(
            {
                "page": i + 1,
                "added": added,
                "removed": removed,
                "changed": bool(added or removed),
            }
        )

    return {
        "pages": pages,
        "total_added": total_added,
        "total_removed": total_removed,
        "identical": total_added == 0 and total_removed == 0,
    }
