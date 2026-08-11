import os

from pdftoolkit import merge, split_every, split_pages, split_ranges
from pdftoolkit.common import page_count


def test_merge_sums_pages(three_page_pdf, two_page_pdf, tmp_path):
    out = str(tmp_path / "merged.pdf")
    n = merge([three_page_pdf, two_page_pdf], out)
    assert n == 5
    assert page_count(out) == 5


def test_split_pages_file_count(five_page_pdf, out_dir):
    outs = split_pages(five_page_pdf, out_dir)
    assert len(outs) == 5
    for o in outs:
        assert os.path.exists(o)
        assert page_count(o) == 1


def test_split_ranges(five_page_pdf, out_dir):
    outs = split_ranges(five_page_pdf, ["1-2", "3-5"], out_dir)
    assert len(outs) == 2
    assert page_count(outs[0]) == 2
    assert page_count(outs[1]) == 3


def test_split_every(five_page_pdf, out_dir):
    outs = split_every(five_page_pdf, 2, out_dir)
    assert len(outs) == 3  # 2 + 2 + 1
    assert [page_count(o) for o in outs] == [2, 2, 1]
