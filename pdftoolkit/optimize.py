"""Web optimisation (linearize) and metadata stripping via pikepdf."""

from __future__ import annotations

import os

import pikepdf

from .common import ensure_parent_dir
from .errors import PdfToolkitError


def _open(input):
    if not os.path.exists(input):
        raise PdfToolkitError(f"input file not found: {input}")
    try:
        return pikepdf.open(input)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"could not open PDF {input!r}: {exc}") from exc


def web_optimize(input, output):
    """Linearize (\"fast web view\") *input* into *output*.

    Linearization reorders the file so the first page can render before the
    whole document is downloaded.

    :returns: *output* path.
    """
    ensure_parent_dir(output)
    pdf = _open(input)
    try:
        pdf.save(output, linearize=True)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"web optimize failed: {exc}") from exc
    finally:
        pdf.close()
    return output


def remove_metadata(input, output):
    """Strip document info dictionary and XMP metadata from *input*.

    :returns: *output* path.
    """
    ensure_parent_dir(output)
    pdf = _open(input)
    try:
        # Drop the classic /Info dictionary (docinfo must be indirect).
        pdf.docinfo = pdf.make_indirect(pikepdf.Dictionary())
        # Drop the XMP metadata stream if present.
        if pikepdf.Name.Metadata in pdf.Root:
            del pdf.Root.Metadata
        pdf.save(output)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"remove metadata failed: {exc}") from exc
    finally:
        pdf.close()
    return output
