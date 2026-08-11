"""Run single-file operations over many inputs."""

from __future__ import annotations

import os

from .compress import compress as _compress_fn
from .convert import pdf_to_images as _pdf_to_images
from .watermark import text_watermark as _text_watermark
from .common import ensure_dir
from .errors import PdfToolkitError


def _out_path(input, out_dir, suffix="", ext=None):
    stem, orig_ext = os.path.splitext(os.path.basename(input))
    ext = ext if ext is not None else orig_ext
    return os.path.join(out_dir, f"{stem}{suffix}{ext}")


def batch_apply(func, inputs, out_dir, suffix="", ext=None, **kwargs):
    """Call ``func(input, output, **kwargs)`` for each input.

    The output path is ``<out_dir>/<stem><suffix><ext>``.  Returns a list of
    ``{"input", "output", "result"}`` dicts (raising on the first failure).
    """
    if not inputs:
        raise PdfToolkitError("batch_apply requires at least one input")
    ensure_dir(out_dir)
    results = []
    for inp in inputs:
        out = _out_path(inp, out_dir, suffix, ext)
        result = func(inp, out, **kwargs)
        results.append({"input": inp, "output": out, "result": result})
    return results


def batch_compress(inputs, out_dir, level="medium"):
    """Compress each input into *out_dir* (``<stem>.pdf``)."""
    return batch_apply(_compress_fn, inputs, out_dir, level=level)


def batch_watermark(inputs, out_dir, text, **kwargs):
    """Apply a text watermark to each input into *out_dir*."""
    def _wm(inp, out, **kw):
        return _text_watermark(inp, out, text, **kw)

    return batch_apply(_wm, inputs, out_dir, **kwargs)


def batch_convert_to_images(inputs, out_dir, fmt="png", dpi=150):
    """Render each input's pages to images under ``<out_dir>/<stem>/``.

    Returns a list of ``{"input", "out_dir", "images"}`` dicts.
    """
    if not inputs:
        raise PdfToolkitError("batch_convert_to_images requires at least one input")
    ensure_dir(out_dir)
    results = []
    for inp in inputs:
        stem = os.path.splitext(os.path.basename(inp))[0]
        sub = os.path.join(out_dir, stem)
        images = _pdf_to_images(inp, sub, fmt=fmt, dpi=dpi)
        results.append({"input": inp, "out_dir": sub, "images": images})
    return results
