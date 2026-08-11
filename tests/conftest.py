"""Shared pytest fixtures: deterministic sample PDFs and images."""

from __future__ import annotations

import os

import pytest
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def _make_pdf(path, pages, prefix="Page"):
    """Create a multi-page PDF with known text on each page."""
    c = canvas.Canvas(path, pagesize=letter)
    for i in range(1, pages + 1):
        c.setFont("Helvetica", 24)
        c.drawString(72, 720, f"{prefix} {i}")
        c.drawString(72, 680, f"Sample document marker LINE_{i}")
        c.drawString(72, 640, "The quick brown fox jumps over the lazy dog.")
        c.showPage()
    c.save()


@pytest.fixture
def three_page_pdf(tmp_path):
    path = tmp_path / "three.pdf"
    _make_pdf(str(path), 3)
    return str(path)


@pytest.fixture
def five_page_pdf(tmp_path):
    path = tmp_path / "five.pdf"
    _make_pdf(str(path), 5)
    return str(path)


@pytest.fixture
def two_page_pdf(tmp_path):
    path = tmp_path / "two.pdf"
    _make_pdf(str(path), 2, prefix="Doc")
    return str(path)


@pytest.fixture
def sample_images(tmp_path):
    """Two deterministic solid-color images (PNG + JPG)."""
    paths = []
    for name, color, fmt in (
        ("red.png", (220, 20, 20), "PNG"),
        ("blue.jpg", (20, 20, 220), "JPEG"),
    ):
        p = tmp_path / name
        Image.new("RGB", (200, 300), color).save(str(p), fmt)
        paths.append(str(p))
    return paths


@pytest.fixture
def out_dir(tmp_path):
    d = tmp_path / "out"
    os.makedirs(d, exist_ok=True)
    return str(d)
