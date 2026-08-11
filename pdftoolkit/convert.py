"""Conversions between PDFs, images and text."""

from __future__ import annotations

import os

from PIL import Image, ImageOps

from .common import ensure_dir, ensure_parent_dir, read_pdf
from .errors import PdfToolkitError
from .pages_util import parse_pages, to_zero_based

# Named page sizes in points (1 pt = 1/72 inch).
_PAGE_SIZES = {
    "a4": (595.0, 842.0),
    "letter": (612.0, 792.0),
    "legal": (612.0, 1008.0),
}


def _resolve_page_size(page_size):
    if page_size is None:
        return None
    if isinstance(page_size, (tuple, list)) and len(page_size) == 2:
        return (float(page_size[0]), float(page_size[1]))
    key = str(page_size).lower()
    if key not in _PAGE_SIZES:
        raise PdfToolkitError(
            f"unknown page_size {page_size!r}; use a (w,h) tuple or one of "
            f"{sorted(_PAGE_SIZES)}"
        )
    return _PAGE_SIZES[key]


def images_to_pdf(images, output, page_size=None):
    """Combine *images* (list of paths, order preserved) into a single PDF.

    Handles PNG/JPG/BMP/TIFF, auto-orients via EXIF, and flattens transparency
    onto white.  If *page_size* is given (a ``(w, h)`` point tuple or a name
    like ``"A4"``/``"letter"``), each image is scaled to fit and centred on a
    white page of that size; otherwise each page matches its image (at 72 dpi).

    :returns: number of pages (== number of images).
    """
    if not images:
        raise PdfToolkitError("images_to_pdf requires at least one image")
    size = _resolve_page_size(page_size)
    ensure_parent_dir(output)

    frames = []
    for path in images:
        if not os.path.exists(path):
            raise PdfToolkitError(f"image not found: {path}")
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)
        except Exception as exc:  # noqa: BLE001
            raise PdfToolkitError(f"could not open image {path!r}: {exc}") from exc

        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")

        if size is not None:
            page = Image.new("RGB", (int(size[0]), int(size[1])), (255, 255, 255))
            fitted = img.copy()
            fitted.thumbnail((int(size[0]), int(size[1])), Image.LANCZOS)
            ox = (page.width - fitted.width) // 2
            oy = (page.height - fitted.height) // 2
            page.paste(fitted, (ox, oy))
            frames.append(page)
        else:
            frames.append(img)

    first, rest = frames[0], frames[1:]
    try:
        first.save(output, "PDF", save_all=True, append_images=rest)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"could not write PDF {output!r}: {exc}") from exc
    return len(frames)


def pdf_to_images(input, out_dir, fmt="png", dpi=150, pages_spec=None):
    """Render pages of *input* to raster images with PDFium (pypdfium2).

    :param fmt: image format/extension (``"png"``, ``"jpg"``, ...).
    :param dpi: render resolution.
    :param pages_spec: which pages (1-based); ``None`` = all.
    :returns: list of output image paths.
    """
    import pypdfium2 as pdfium

    if not os.path.exists(input):
        raise PdfToolkitError(f"input file not found: {input}")
    ensure_dir(out_dir)
    fmt = fmt.lower().lstrip(".")
    pil_fmt = "JPEG" if fmt in ("jpg", "jpeg") else fmt.upper()

    try:
        pdf = pdfium.PdfDocument(input)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"could not open PDF {input!r}: {exc}") from exc

    try:
        total = len(pdf)
        pages = parse_pages(pages_spec, total)
        stem = os.path.splitext(os.path.basename(input))[0]
        scale = float(dpi) / 72.0
        outputs = []
        for p in pages:
            page = pdf[p - 1]
            bitmap = page.render(scale=scale)
            pil = bitmap.to_pil()
            if pil_fmt == "JPEG" and pil.mode != "RGB":
                pil = pil.convert("RGB")
            out = os.path.join(out_dir, f"{stem}_page_{p}.{fmt}")
            pil.save(out, pil_fmt)
            outputs.append(out)
        return outputs
    finally:
        pdf.close()


def pdf_to_text(input, output=None, pages_spec=None):
    """Extract text with pypdf.

    :param output: if given, text is written there (UTF-8); otherwise returned.
    :param pages_spec: which pages (1-based); ``None`` = all.
    :returns: the extracted text (always returned, even when also written).
    """
    reader = read_pdf(input)
    total = len(reader.pages)
    pages = parse_pages(pages_spec, total)
    chunks = []
    for i in to_zero_based(pages):
        try:
            chunks.append(reader.pages[i].extract_text() or "")
        except Exception:  # noqa: BLE001 - skip unextractable page
            chunks.append("")
    text = "\n".join(chunks)
    if output is not None:
        ensure_parent_dir(output)
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text)
    return text


def extract_images(input, out_dir):
    """Pull embedded raster images out of *input* using pypdf.

    :returns: list of written image paths (in page then object order).
    """
    reader = read_pdf(input)
    ensure_dir(out_dir)
    stem = os.path.splitext(os.path.basename(input))[0]
    outputs = []
    counter = 0
    for pnum, page in enumerate(reader.pages, start=1):
        try:
            images = page.images
        except Exception:  # noqa: BLE001
            continue
        for img in images:
            counter += 1
            name = img.name or f"img{counter}"
            base = f"{stem}_p{pnum}_{counter}_{os.path.basename(name)}"
            if "." not in base:
                base += ".png"
            out = os.path.join(out_dir, base)
            try:
                with open(out, "wb") as fh:
                    fh.write(img.data)
                outputs.append(out)
            except Exception:  # noqa: BLE001
                continue
    return outputs
