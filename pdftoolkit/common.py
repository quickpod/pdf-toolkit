"""Shared low-level helpers used across pdftoolkit modules."""

from __future__ import annotations

import io
import os

from pypdf import PdfReader, PdfWriter

from .errors import PdfToolkitError


def read_pdf(path):
    """Open *path* as a :class:`pypdf.PdfReader`, wrapping errors."""
    if not os.path.exists(path):
        raise PdfToolkitError(f"input file not found: {path}")
    try:
        return PdfReader(path)
    except Exception as exc:  # noqa: BLE001 - normalise to our error type
        raise PdfToolkitError(f"could not read PDF {path!r}: {exc}") from exc


def page_count(path):
    """Return the number of pages in *path*."""
    return len(read_pdf(path).pages)


def ensure_parent_dir(path):
    """Make sure the parent directory of *path* exists."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def ensure_dir(path):
    """Make sure directory *path* exists."""
    if path:
        os.makedirs(path, exist_ok=True)


def write_pdf(writer, output):
    """Write *writer* to *output*, creating parent directories as needed."""
    ensure_parent_dir(output)
    try:
        with open(output, "wb") as fh:
            writer.write(fh)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"could not write PDF {output!r}: {exc}") from exc


def overlay_from_draw(draw_fn, width, height):
    """Build a single-page overlay via a reportlab draw callback.

    *draw_fn* receives a reportlab ``canvas.Canvas`` sized ``(width, height)``
    in points.  Returns a pypdf page object suitable for ``merge_page``.
    """
    from reportlab.pdfgen import canvas  # local import: keeps import time low

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    draw_fn(c)
    c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def position_point(width, height, position, margin=36.0):
    """Return an (x, y) anchor point for a named position (points, PDF origin).

    Supported: center, top-left, top-right, bottom-left, bottom-right,
    top-center, bottom-center.
    """
    positions = {
        "center": (width / 2.0, height / 2.0),
        "top-left": (margin, height - margin),
        "top-right": (width - margin, height - margin),
        "bottom-left": (margin, margin),
        "bottom-right": (width - margin, margin),
        "top-center": (width / 2.0, height - margin),
        "bottom-center": (width / 2.0, margin),
    }
    if position not in positions:
        raise PdfToolkitError(
            f"unknown position {position!r}; choose from {sorted(positions)}"
        )
    return positions[position]


def human_size(num_bytes):
    """Human-readable byte size, e.g. ``1.1MB``."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)}{unit}"
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"


__all__ = [
    "read_pdf",
    "page_count",
    "ensure_parent_dir",
    "ensure_dir",
    "write_pdf",
    "overlay_from_draw",
    "position_point",
    "human_size",
    "PdfReader",
    "PdfWriter",
]
