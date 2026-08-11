"""Text and image watermarks, composited with reportlab + pypdf."""

from __future__ import annotations

import os

from .common import PdfWriter, overlay_from_draw, position_point, read_pdf, write_pdf
from .errors import PdfToolkitError
from .pages_util import parse_pages

_TILE_STEP = 200.0


def _rgb01(color):
    return (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)


def _selected(pages_spec, total):
    if pages_spec:
        return set(parse_pages(pages_spec, total))
    return set(range(1, total + 1))


def text_watermark(
    input,
    output,
    text,
    opacity=0.3,
    position="center",
    rotation=45,
    font_size=48,
    color=(128, 128, 128),
    pages_spec=None,
):
    """Stamp *text* across selected pages.

    :param position: ``center``, a corner (``top-left`` etc.), ``top-center`` /
        ``bottom-center``, or ``tiled`` (repeated across the whole page).
    :param opacity: 0..1 fill alpha.
    :param rotation: text rotation in degrees.
    :returns: page count of the output (unchanged from input).
    """
    if not text:
        raise PdfToolkitError("watermark text must not be empty")
    total = len(read_pdf(input).pages)
    sel = _selected(pages_spec, total)

    def make_draw(width, height):
        def draw(c):
            c.setFillColorRGB(*_rgb01(color))
            c.setFillAlpha(opacity)
            c.setFont("Helvetica", font_size)
            if position == "tiled":
                y = 0.0
                while y < height + _TILE_STEP:
                    x = 0.0
                    while x < width + _TILE_STEP:
                        c.saveState()
                        c.translate(x, y)
                        c.rotate(rotation)
                        c.drawCentredString(0, 0, text)
                        c.restoreState()
                        x += _TILE_STEP
                    y += _TILE_STEP
            else:
                x, y = position_point(width, height, position)
                c.saveState()
                c.translate(x, y)
                c.rotate(rotation)
                c.drawCentredString(0, 0, text)
                c.restoreState()

        return draw

    writer = PdfWriter(clone_from=input)
    for i, page in enumerate(writer.pages, start=1):
        if i in sel:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            overlay = overlay_from_draw(make_draw(width, height), width, height)
            page.merge_page(overlay)
    write_pdf(writer, output)
    return total


def image_watermark(
    input,
    output,
    image_path,
    opacity=0.3,
    position="center",
    scale=0.5,
    pages_spec=None,
):
    """Stamp an image (from *image_path*) across selected pages.

    The image is drawn at *scale* times the page width, keeping aspect ratio,
    with *opacity* applied via a soft mask.

    :returns: page count of the output (unchanged from input).
    """
    from io import BytesIO

    from PIL import Image
    from reportlab.lib.utils import ImageReader

    if not os.path.exists(image_path):
        raise PdfToolkitError(f"watermark image not found: {image_path}")

    src = Image.open(image_path).convert("RGBA")
    # Fold the requested opacity into the alpha channel.
    alpha = src.split()[-1].point(lambda a: int(a * opacity))
    src.putalpha(alpha)
    img_reader = ImageReader(src)
    iw, ih = src.size
    aspect = ih / iw if iw else 1.0

    total = len(read_pdf(input).pages)
    sel = _selected(pages_spec, total)

    def make_draw(width, height):
        def draw(c):
            draw_w = width * scale
            draw_h = draw_w * aspect
            if position == "tiled":
                step_x = draw_w * 1.2
                step_y = draw_h * 1.2
                y = 0.0
                while y < height:
                    x = 0.0
                    while x < width:
                        c.drawImage(
                            img_reader, x, y, draw_w, draw_h, mask="auto"
                        )
                        x += step_x
                    y += step_y
            else:
                cx, cy = position_point(width, height, position)
                x = cx - draw_w / 2.0
                y = cy - draw_h / 2.0
                c.drawImage(img_reader, x, y, draw_w, draw_h, mask="auto")

        return draw

    writer = PdfWriter(clone_from=input)
    for i, page in enumerate(writer.pages, start=1):
        if i in sel:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            overlay = overlay_from_draw(make_draw(width, height), width, height)
            page.merge_page(overlay)
    write_pdf(writer, output)
    return total
