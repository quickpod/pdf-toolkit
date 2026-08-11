"""Best-effort PDF repair via pikepdf/qpdf recovery."""

from __future__ import annotations

import os

import pikepdf

from .common import ensure_parent_dir
from .errors import PdfToolkitError


def repair(input, output):
    """Open *input* with qpdf's recovery and re-save a clean copy.

    qpdf reconstructs the cross-reference table and object structure where it
    can.  Genuinely destroyed content cannot be recovered.

    :returns: *output* path.
    """
    if not os.path.exists(input):
        raise PdfToolkitError(f"input file not found: {input}")
    ensure_parent_dir(output)
    try:
        pdf = pikepdf.open(input)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"could not open PDF for repair: {exc}") from exc
    try:
        pdf.save(output, fix_metadata_version=True)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"repair save failed: {exc}") from exc
    finally:
        pdf.close()
    return output
