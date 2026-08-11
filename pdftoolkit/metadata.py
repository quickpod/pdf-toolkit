"""Read and write document metadata; summarise a document."""

from __future__ import annotations

import os

from .common import PdfWriter, read_pdf, write_pdf

_KEYMAP = {
    "/Title": "title",
    "/Author": "author",
    "/Subject": "subject",
    "/Keywords": "keywords",
    "/Creator": "creator",
    "/Producer": "producer",
    "/CreationDate": "creation_date",
    "/ModDate": "mod_date",
}


def get_metadata(input):
    """Return document metadata as a plain dict (friendly keys).

    Keys: title, author, subject, keywords, creator, producer, creation_date,
    mod_date.  Missing values are ``None``.
    """
    reader = read_pdf(input)
    result = {v: None for v in _KEYMAP.values()}
    try:
        meta = reader.metadata or {}
        for raw, value in dict(meta).items():
            friendly = _KEYMAP.get(raw)
            if friendly:
                result[friendly] = None if value is None else str(value)
    except Exception:  # noqa: BLE001 - encrypted/undecryptable: leave blanks
        pass
    return result


def set_metadata(input, output, title=None, author=None, subject=None, keywords=None):
    """Write metadata to *output*, preserving existing fields not overridden.

    Only non-``None`` arguments are applied.

    :returns: *output* path.
    """
    reader = read_pdf(input)
    writer = PdfWriter()
    writer.append(reader)

    meta = {}
    if reader.metadata:
        for key, value in dict(reader.metadata).items():
            if value is not None:
                meta[key] = str(value)

    for key, value in (
        ("/Title", title),
        ("/Author", author),
        ("/Subject", subject),
        ("/Keywords", keywords),
    ):
        if value is not None:
            meta[key] = value

    writer.add_metadata(meta)
    write_pdf(writer, output)
    return output


def info(input):
    """Summarise a document.

    :returns: dict with ``path``, ``file_size``, ``page_count``, ``encrypted``,
        ``page_sizes`` (list of ``(width, height)`` in points) and
        ``metadata`` (as from :func:`get_metadata`).
    """
    reader = read_pdf(input)
    encrypted = bool(reader.is_encrypted)
    file_size = os.path.getsize(input) if os.path.exists(input) else None

    # An encrypted file cannot be paged/inspected without the password; report
    # what we can (size + encrypted flag) rather than crash.
    if encrypted:
        return {
            "path": input,
            "file_size": file_size,
            "page_count": None,
            "encrypted": True,
            "page_sizes": [],
            "metadata": get_metadata(input),
        }

    page_sizes = []
    for page in reader.pages:
        page_sizes.append(
            (round(float(page.mediabox.width), 2), round(float(page.mediabox.height), 2))
        )
    return {
        "path": input,
        "file_size": file_size,
        "page_count": len(reader.pages),
        "encrypted": False,
        "page_sizes": page_sizes,
        "metadata": get_metadata(input),
    }
