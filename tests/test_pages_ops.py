import pytest

from pdftoolkit import PdfToolkitError, delete, duplicate, extract, reorder, rotate
from pdftoolkit.common import page_count, read_pdf


def test_extract(five_page_pdf, tmp_path):
    out = str(tmp_path / "ex.pdf")
    n = extract(five_page_pdf, out, "1,3,5")
    assert n == 3
    assert page_count(out) == 3


def test_delete(five_page_pdf, tmp_path):
    out = str(tmp_path / "del.pdf")
    n = delete(five_page_pdf, out, "2,4")
    assert n == 3
    assert page_count(out) == 3


def test_delete_all_raises(three_page_pdf, tmp_path):
    with pytest.raises(PdfToolkitError):
        delete(three_page_pdf, str(tmp_path / "x.pdf"), "1-3")


def test_rotate_metadata(three_page_pdf, tmp_path):
    out = str(tmp_path / "rot.pdf")
    n = rotate(three_page_pdf, out, 90, "1")
    assert n == 3
    reader = read_pdf(out)
    assert reader.pages[0].get("/Rotate", 0) == 90
    assert reader.pages[1].get("/Rotate", 0) == 0


def test_rotate_invalid_degrees(three_page_pdf, tmp_path):
    with pytest.raises(PdfToolkitError):
        rotate(three_page_pdf, str(tmp_path / "x.pdf"), 45)


def test_reorder(three_page_pdf, tmp_path):
    out = str(tmp_path / "re.pdf")
    n = reorder(three_page_pdf, out, [3, 1, 2])
    assert n == 3
    text = read_pdf(out).pages[0].extract_text()
    assert "Page 3" in text


def test_reorder_not_permutation(three_page_pdf, tmp_path):
    with pytest.raises(PdfToolkitError):
        reorder(three_page_pdf, str(tmp_path / "x.pdf"), [1, 2])


def test_duplicate(three_page_pdf, tmp_path):
    out = str(tmp_path / "dup.pdf")
    n = duplicate(three_page_pdf, out, "2")
    assert n == 4
    assert page_count(out) == 4
