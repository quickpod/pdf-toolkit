from pdftoolkit import get_metadata, info, set_metadata


def test_set_get_roundtrip(three_page_pdf, tmp_path):
    out = str(tmp_path / "meta.pdf")
    set_metadata(
        three_page_pdf,
        out,
        title="My Title",
        author="Jane Doe",
        subject="Testing",
        keywords="a,b,c",
    )
    meta = get_metadata(out)
    assert meta["title"] == "My Title"
    assert meta["author"] == "Jane Doe"
    assert meta["subject"] == "Testing"
    assert meta["keywords"] == "a,b,c"


def test_set_metadata_preserves_and_overrides(three_page_pdf, tmp_path):
    out1 = str(tmp_path / "m1.pdf")
    out2 = str(tmp_path / "m2.pdf")
    set_metadata(three_page_pdf, out1, title="T1", author="A1")
    set_metadata(out1, out2, title="T2")  # author should survive
    meta = get_metadata(out2)
    assert meta["title"] == "T2"
    assert meta["author"] == "A1"


def test_info(three_page_pdf):
    d = info(three_page_pdf)
    assert d["page_count"] == 3
    assert d["encrypted"] is False
    assert d["file_size"] > 0
    assert len(d["page_sizes"]) == 3
    # letter size ~ 612 x 792 pt
    assert round(d["page_sizes"][0][0]) == 612
    assert round(d["page_sizes"][0][1]) == 792
