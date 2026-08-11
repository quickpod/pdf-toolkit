"""Page numbers and header/footer stamps."""

from __future__ import annotations

from .common import PdfWriter, overlay_from_draw, position_point, read_pdf, write_pdf
from .errors import PdfToolkitError

_FONT = "Helvetica"
_FONT_SIZE = 10


def _draw_string(c, width, height, position, text, font_size=_FONT_SIZE):
    c.setFont(_FONT, font_size)
    c.setFillColorRGB(0, 0, 0)
    x, y = position_point(width, height, position)
    if position.endswith("left"):
        c.drawString(x, y, text)
    elif position.endswith("right"):
        c.drawRightString(x, y, text)
    else:  # any *-center / center
        c.drawCentredString(x, y, text)


def add_page_numbers(
    input, output, position="bottom-center", start=1, fmt="{n}"
):
    """Stamp page numbers onto every page.

    :param position: any named position (default ``bottom-center``).
    :param start: number to print on the first page.
    :param fmt: format string with ``{n}`` (this page's number) and ``{total}``.
    :returns: page count.
    """
    total = len(read_pdf(input).pages)
    writer = PdfWriter(clone_from=input)
    for idx, page in enumerate(writer.pages):
        n = start + idx
        try:
            label = fmt.format(n=n, total=total, page=n)
        except (KeyError, IndexError, ValueError) as exc:
            raise PdfToolkitError(f"invalid page-number format {fmt!r}: {exc}") from exc
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        overlay = overlay_from_draw(
            lambda c, w=width, h=height, t=label: _draw_string(c, w, h, position, t),
            width,
            height,
        )
        page.merge_page(overlay)
    write_pdf(writer, output)
    return total


def add_header_footer(input, output, header=None, footer=None):
    """Stamp a centred *header* (top) and/or *footer* (bottom) onto every page.

    :returns: page count.
    """
    if header is None and footer is None:
        raise PdfToolkitError("provide at least one of header or footer")
    total = len(read_pdf(input).pages)
    writer = PdfWriter(clone_from=input)
    for page in writer.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        def draw(c, w=width, h=height):
            if header:
                _draw_string(c, w, h, "top-center", header)
            if footer:
                _draw_string(c, w, h, "bottom-center", footer)

        overlay = overlay_from_draw(draw, width, height)
        page.merge_page(overlay)
    write_pdf(writer, output)
    return total
