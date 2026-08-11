"""Lossy/lossless compression and optimisation via pikepdf + Pillow."""

from __future__ import annotations

import io
import os
import shutil

import pikepdf
from PIL import Image

from .errors import PdfToolkitError

# level -> (max image dimension in px, JPEG quality)
# "low" = least aggressive (best quality), "high" = most aggressive.
_LEVELS = {
    "low": (1800, 85),
    "medium": (1200, 72),
    "high": (800, 55),
}


def _recompress_image(obj, max_dim, quality):
    """Downscale/recompress a single image XObject in place.

    Returns True if the object was rewritten.  Raises on anything unexpected;
    the caller keeps the original image on failure.
    """
    pimg = pikepdf.PdfImage(obj)
    pil = pimg.as_pil_image()
    w, h = pil.size
    scale = min(1.0, float(max_dim) / float(max(w, h)))

    # Nothing to gain: already small and already a JPEG.
    already_jpeg = pikepdf.Name.DCTDecode in _filters(obj)
    if scale >= 1.0 and already_jpeg:
        return False

    if scale < 1.0:
        pil = pil.resize(
            (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS
        )
    if pil.mode not in ("RGB", "L"):
        pil = pil.convert("RGB")

    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=quality, optimize=True)
    data = buf.getvalue()

    obj.write(data, filter=pikepdf.Name.DCTDecode)
    obj.ColorSpace = (
        pikepdf.Name.DeviceGray if pil.mode == "L" else pikepdf.Name.DeviceRGB
    )
    obj.Width, obj.Height = pil.size
    obj.BitsPerComponent = 8
    for key in ("/SMask", "/Decode", "/DecodeParms"):
        if key in obj:
            del obj[key]
    return True


def _filters(obj):
    flt = obj.get("/Filter")
    if flt is None:
        return []
    if isinstance(flt, pikepdf.Name):
        return [flt]
    return list(flt)


def compress(input, output, level="medium"):
    """Compress *input* to *output*.

    Strategy (all best-effort and robust):
      * downscale + JPEG-recompress large image XObjects (per-*level* target),
      * regenerate object streams, recompress flate streams,
      * drop unreferenced objects.

    Image failures on individual objects are swallowed (original kept).  The
    result is guaranteed valid and never larger than the input: if processing
    would grow the file, the original is copied through unchanged.

    :param level: one of ``"low"``, ``"medium"``, ``"high"``.
    :returns: dict with ``original_size``, ``new_size``, ``ratio`` (fraction
        saved, 0..1) and ``level``.
    """
    if level not in _LEVELS:
        raise PdfToolkitError(f"level must be one of {sorted(_LEVELS)}; got {level!r}")
    if not os.path.exists(input):
        raise PdfToolkitError(f"input file not found: {input}")

    max_dim, quality = _LEVELS[level]
    original_size = os.path.getsize(input)

    try:
        pdf = pikepdf.open(input)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"could not open PDF {input!r}: {exc}") from exc

    seen = set()
    for page in pdf.pages:
        try:
            images = page.images
        except Exception:  # noqa: BLE001
            continue
        for _name, obj in images.items():
            key = obj.objgen if hasattr(obj, "objgen") else id(obj)
            if key in seen:
                continue
            seen.add(key)
            try:
                _recompress_image(obj, max_dim, quality)
            except Exception:  # noqa: BLE001 - keep original image, continue
                continue

    tmp = output + ".tmp"
    try:
        pdf.remove_unreferenced_resources()
        pdf.save(
            tmp,
            compress_streams=True,
            recompress_flate=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
            linearize=False,
        )
    except Exception as exc:  # noqa: BLE001
        if os.path.exists(tmp):
            os.remove(tmp)
        raise PdfToolkitError(f"compression failed: {exc}") from exc
    finally:
        pdf.close()

    new_size = os.path.getsize(tmp)
    if new_size > original_size:
        # Never grow the file: fall back to the original bytes.
        os.remove(tmp)
        shutil.copyfile(input, output)
        new_size = original_size
    else:
        os.replace(tmp, output)

    ratio = 0.0 if original_size == 0 else 1.0 - (new_size / original_size)
    return {
        "original_size": original_size,
        "new_size": new_size,
        "ratio": ratio,
        "level": level,
    }
