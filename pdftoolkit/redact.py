"""Rectangle redaction.

LIMITATION (read carefully): this draws opaque black boxes over the given
rectangles and flattens them onto the page content, which reliably hides the
*visual* content.  It attempts to also drop text-showing operators whose
position falls inside a redaction rectangle, but PDF text positioning is
complex (transforms, kerning arrays, form XObjects) so **removal of the
underlying text is best-effort and not guaranteed**.  For high-assurance
redaction, rasterise the page (``convert.pdf_to_images``) and rebuild the PDF
from the images, which destroys all vector text.  This function does not do
that automatically because it would change the file from text to image.
"""

from __future__ import annotations

from .common import PdfWriter, overlay_from_draw, read_pdf, write_pdf
from .errors import PdfToolkitError


def redact_rects(input, output, page, rects):
    """Cover *rects* on *page* (1-based) with opaque black boxes.

    :param rects: list of ``(x0, y0, x1, y1)`` in PDF points, origin at the
        bottom-left of the page.
    :returns: number of rectangles drawn.

    See the module docstring for the (honest) limitations of text removal.
    """
    if not rects:
        raise PdfToolkitError("redact_rects requires at least one rectangle")
    reader = read_pdf(input)
    total = len(reader.pages)
    if page < 1 or page > total:
        raise PdfToolkitError(f"page {page} out of range (1..{total})")

    target = reader.pages[page - 1]
    width = float(target.mediabox.width)
    height = float(target.mediabox.height)

    def draw(c):
        c.setFillColorRGB(0, 0, 0)
        c.setStrokeColorRGB(0, 0, 0)
        for (x0, y0, x1, y1) in rects:
            lx, rx = sorted((float(x0), float(x1)))
            ly, uy = sorted((float(y0), float(y1)))
            c.rect(lx, ly, rx - lx, uy - ly, fill=1, stroke=0)

    overlay = overlay_from_draw(draw, width, height)

    writer = PdfWriter(clone_from=input)
    writer.pages[page - 1].merge_page(overlay)
    write_pdf(writer, output)
    return len(rects)
