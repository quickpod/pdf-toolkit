import os

from pdftoolkit import (
    add_bookmark,
    compare_text,
    extract_images,
    generate_toc,
    list_bookmarks,
    merge,
    redact_rects,
    repair,
)
from pdftoolkit.batch import batch_compress
from pdftoolkit.common import page_count


def test_bookmarks_roundtrip(three_page_pdf, tmp_path):
    out = str(tmp_path / "bm.pdf")
    generate_toc(three_page_pdf, out, [("Intro", 1), ("Middle", 2), ("End", 3)])
    items = list_bookmarks(out)
    titles = [i["title"] for i in items]
    assert titles == ["Intro", "Middle", "End"]
    assert items[1]["page"] == 2


def test_add_single_bookmark(three_page_pdf, tmp_path):
    out = str(tmp_path / "bm1.pdf")
    add_bookmark(three_page_pdf, out, "Chapter 1", 2)
    items = list_bookmarks(out)
    assert any(i["title"] == "Chapter 1" and i["page"] == 2 for i in items)


def test_redact(three_page_pdf, tmp_path):
    out = str(tmp_path / "red.pdf")
    n = redact_rects(three_page_pdf, out, 1, [(72, 700, 300, 740)])
    assert n == 1
    assert page_count(out) == 3


def test_compare_text_identical(three_page_pdf):
    d = compare_text(three_page_pdf, three_page_pdf)
    assert d["identical"] is True
    assert d["total_added"] == 0


def test_compare_text_differs(three_page_pdf, two_page_pdf):
    d = compare_text(three_page_pdf, two_page_pdf)
    assert d["identical"] is False
    assert d["total_added"] + d["total_removed"] > 0


def test_repair(three_page_pdf, tmp_path):
    out = str(tmp_path / "rep.pdf")
    repair(three_page_pdf, out)
    assert page_count(out) == 3


def test_extract_images(sample_images, tmp_path, out_dir):
    from pdftoolkit import images_to_pdf

    pdf = str(tmp_path / "img.pdf")
    images_to_pdf(sample_images, pdf)
    outs = extract_images(pdf, out_dir)
    assert len(outs) >= 1
    for o in outs:
        assert os.path.getsize(o) > 0


def test_batch_compress(three_page_pdf, two_page_pdf, out_dir):
    res = batch_compress([three_page_pdf, two_page_pdf], out_dir, level="medium")
    assert len(res) == 2
    for r in res:
        assert os.path.exists(r["output"])
