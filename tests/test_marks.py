from pdftoolkit import add_header_footer, add_page_numbers, image_watermark, text_watermark
from pdftoolkit.common import page_count, read_pdf


def _text_len(path):
    return sum(len(p.extract_text() or "") for p in read_pdf(path).pages)


def test_text_watermark_keeps_pages_and_adds_content(three_page_pdf, tmp_path):
    out = str(tmp_path / "wm.pdf")
    before = _text_len(three_page_pdf)
    n = text_watermark(three_page_pdf, out, "CONFIDENTIAL")
    assert n == 3
    assert page_count(out) == 3
    assert _text_len(out) > before  # watermark text added


def test_text_watermark_subset(three_page_pdf, tmp_path):
    out = str(tmp_path / "wm.pdf")
    n = text_watermark(three_page_pdf, out, "DRAFT", pages_spec="1")
    assert n == 3
    assert page_count(out) == 3


def test_image_watermark(three_page_pdf, sample_images, tmp_path):
    out = str(tmp_path / "iwm.pdf")
    n = image_watermark(three_page_pdf, out, sample_images[0])
    assert n == 3
    assert page_count(out) == 3


def test_page_numbers(three_page_pdf, tmp_path):
    out = str(tmp_path / "pn.pdf")
    n = add_page_numbers(three_page_pdf, out, fmt="Page {n} of {total}")
    assert n == 3
    assert "Page 1 of 3" in read_pdf(out).pages[0].extract_text()


def test_header_footer(three_page_pdf, tmp_path):
    out = str(tmp_path / "hf.pdf")
    n = add_header_footer(three_page_pdf, out, header="TOP", footer="BOTTOM")
    assert n == 3
    text = read_pdf(out).pages[0].extract_text()
    assert "TOP" in text and "BOTTOM" in text
