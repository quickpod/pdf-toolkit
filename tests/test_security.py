import pytest

from pdftoolkit import PdfToolkitError, info, is_encrypted, protect, unprotect
from pdftoolkit.common import page_count


def test_info_on_encrypted_does_not_crash(three_page_pdf, tmp_path):
    enc = str(tmp_path / "enc.pdf")
    protect(three_page_pdf, enc, user_password="secret")
    d = info(enc)
    assert d["encrypted"] is True
    assert d["page_count"] is None
    assert d["file_size"] > 0


def test_protect_and_detect(three_page_pdf, tmp_path):
    enc = str(tmp_path / "enc.pdf")
    protect(three_page_pdf, enc, user_password="secret")
    assert is_encrypted(enc) is True
    assert is_encrypted(three_page_pdf) is False


def test_unprotect_roundtrip(three_page_pdf, tmp_path):
    enc = str(tmp_path / "enc.pdf")
    dec = str(tmp_path / "dec.pdf")
    protect(three_page_pdf, enc, user_password="secret")
    unprotect(enc, dec, "secret")
    assert is_encrypted(dec) is False
    assert page_count(dec) == 3


def test_wrong_password_raises(three_page_pdf, tmp_path):
    enc = str(tmp_path / "enc.pdf")
    protect(three_page_pdf, enc, user_password="secret")
    with pytest.raises(PdfToolkitError):
        unprotect(enc, str(tmp_path / "dec.pdf"), "wrong")
