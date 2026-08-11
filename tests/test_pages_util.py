import pytest

from pdftoolkit import PdfToolkitError, parse_pages


def test_simple_range():
    assert parse_pages("1-3,5,8-10", 10) == [1, 2, 3, 5, 8, 9, 10]


def test_single_and_whitespace():
    assert parse_pages(" 2 , 4 ", 5) == [2, 4]


def test_empty_selects_all():
    assert parse_pages("", 3) == [1, 2, 3]
    assert parse_pages(None, 3) == [1, 2, 3]


def test_descending_range():
    assert parse_pages("3-1", 3) == [3, 2, 1]


def test_order_and_duplicates_preserved():
    assert parse_pages("3,1,1", 3) == [3, 1, 1]


def test_out_of_range_raises():
    with pytest.raises(PdfToolkitError):
        parse_pages("1-4", 3)
    with pytest.raises(PdfToolkitError):
        parse_pages("0", 3)


def test_malformed_raises():
    with pytest.raises(PdfToolkitError):
        parse_pages("1-", 3)
    with pytest.raises(PdfToolkitError):
        parse_pages("abc", 3)
