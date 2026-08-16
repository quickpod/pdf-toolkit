"""pdftoolkit -- a permissively-licensed PDF utilities library.

Public API: every function takes explicit input/output paths, uses 1-based page
numbers, and raises :class:`PdfToolkitError` on failure.  Import what you need::

    from pdftoolkit import merge, compress, protect
    merge(["a.pdf", "b.pdf"], "out.pdf")

A future GUI is expected to build on this module.  See ``README-API.md`` for
the full signature reference.
"""

from __future__ import annotations

from .errors import PdfToolkitError
from .pages_util import parse_pages
from .merge import merge
from .split import split_pages, split_ranges, split_every
from .pages import extract, delete, rotate, reorder, duplicate
from .compress import compress
from .optimize import web_optimize, remove_metadata
from .convert import images_to_pdf, pdf_to_images, pdf_to_text, extract_images
from .security import protect, unprotect, is_encrypted
from .watermark import text_watermark, image_watermark
from .stamp import add_page_numbers, add_header_footer
from .metadata import get_metadata, set_metadata, info
from .bookmarks import add_bookmark, list_bookmarks, generate_toc
from .redact import redact_rects
from .compare import compare_text
from .repair import repair
from .batch import (
    batch_apply,
    batch_compress,
    batch_watermark,
    batch_convert_to_images,
)

__version__ = "1.1.0"

__all__ = [
    "PdfToolkitError",
    "parse_pages",
    "merge",
    "split_pages",
    "split_ranges",
    "split_every",
    "extract",
    "delete",
    "rotate",
    "reorder",
    "duplicate",
    "compress",
    "web_optimize",
    "remove_metadata",
    "images_to_pdf",
    "pdf_to_images",
    "pdf_to_text",
    "extract_images",
    "protect",
    "unprotect",
    "is_encrypted",
    "text_watermark",
    "image_watermark",
    "add_page_numbers",
    "add_header_footer",
    "get_metadata",
    "set_metadata",
    "info",
    "add_bookmark",
    "list_bookmarks",
    "generate_toc",
    "redact_rects",
    "compare_text",
    "repair",
    "batch_apply",
    "batch_compress",
    "batch_watermark",
    "batch_convert_to_images",
]
