import os

from pdftoolkit import images_to_pdf, pdf_to_images, pdf_to_text
from pdftoolkit.common import page_count


def test_images_to_pdf(sample_images, tmp_path):
    out = str(tmp_path / "img.pdf")
    n = images_to_pdf(sample_images, out)
    assert n == 2
    assert page_count(out) == 2


def test_images_to_pdf_with_page_size(sample_images, tmp_path):
    out = str(tmp_path / "img_a4.pdf")
    n = images_to_pdf(sample_images, out, page_size="A4")
    assert n == 2
    assert page_count(out) == 2


def test_images_pdf_images_roundtrip(sample_images, out_dir, tmp_path):
    pdf = str(tmp_path / "img.pdf")
    images_to_pdf(sample_images, pdf)
    outs = pdf_to_images(pdf, out_dir, dpi=72)
    assert len(outs) == 2
    for o in outs:
        assert os.path.exists(o) and os.path.getsize(o) > 0


def test_pdf_to_text_finds_known_text(three_page_pdf):
    text = pdf_to_text(three_page_pdf)
    assert "Page 1" in text
    assert "LINE_2" in text


def test_pdf_to_text_pages_subset(five_page_pdf):
    text = pdf_to_text(five_page_pdf, pages_spec="3")
    assert "Page 3" in text
    assert "Page 1" not in text


def test_pdf_to_text_to_file(three_page_pdf, tmp_path):
    out = str(tmp_path / "t.txt")
    pdf_to_text(three_page_pdf, out)
    with open(out, encoding="utf-8") as fh:
        assert "Page 1" in fh.read()
