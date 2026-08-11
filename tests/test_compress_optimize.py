import os

import pikepdf

from pdftoolkit import compress, images_to_pdf, remove_metadata, set_metadata, web_optimize
from pdftoolkit.common import page_count
from pdftoolkit.metadata import get_metadata


def _image_heavy_pdf(images, tmp_path):
    # Build a PDF from images so there is something to actually compress.
    out = str(tmp_path / "heavy.pdf")
    images_to_pdf(images * 3, out)  # 6 image pages
    return out


def test_compress_not_larger_and_valid(sample_images, tmp_path):
    src = _image_heavy_pdf(sample_images, tmp_path)
    out = str(tmp_path / "small.pdf")
    r = compress(src, out, level="high")
    assert os.path.getsize(out) <= os.path.getsize(src)
    assert r["new_size"] <= r["original_size"]
    # still valid + same page count
    assert page_count(out) == page_count(src)


def test_compress_levels_valid(three_page_pdf, tmp_path):
    for level in ("low", "medium", "high"):
        out = str(tmp_path / f"c_{level}.pdf")
        r = compress(three_page_pdf, out, level=level)
        assert page_count(out) == 3
        assert r["new_size"] <= r["original_size"]


def test_web_optimize_linearized(three_page_pdf, tmp_path):
    out = str(tmp_path / "web.pdf")
    web_optimize(three_page_pdf, out)
    assert page_count(out) == 3
    with pikepdf.open(out) as pdf:
        assert pdf.is_linearized


def test_remove_metadata(three_page_pdf, tmp_path):
    withmeta = str(tmp_path / "wm.pdf")
    set_metadata(three_page_pdf, withmeta, title="Secret", author="Nobody")
    stripped = str(tmp_path / "stripped.pdf")
    remove_metadata(withmeta, stripped)
    meta = get_metadata(stripped)
    assert meta["title"] is None
    assert meta["author"] is None
