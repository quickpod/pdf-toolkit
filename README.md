# PDF Toolkit

A fast, **offline**, **100% open-source** PDF toolkit for Windows — merge, split,
compress, convert, protect, watermark and more. Nothing is uploaded anywhere;
every operation runs on your own machine. Built entirely by AI with human
testing and guidance, and published on [QuickOpen](https://quickopen.ai/projects/pdf-toolkit).

## What it does

**Organize** — merge/combine, split (per-page, by ranges, every N), extract
pages, delete pages, rotate (90/180/270), rearrange page order, duplicate pages.

**Convert** — Images → PDF (PNG/JPG/BMP/TIFF), PDF → Images (PNG/JPG at any DPI),
PDF → Text, extract embedded images.

**Optimize** — compress (low / medium / high), optimize for web viewing
(linearize), remove metadata. Batch compression.

**Security** — password-protect (AES-256), remove a password, and set
permissions (restrict printing / copying / editing / annotating).

**Watermark & stamp** — text or image watermarks with opacity, position
(corners, center, tiled) and rotation; add page numbers and headers/footers.

**Metadata & navigation** — view PDF properties, edit title/author/subject/
keywords, strip metadata, list bookmarks.

**Advanced** — redact regions, compare two PDFs (per-page text diff), repair
damaged files.

**Batch** — run compress, watermark, or convert-to-images across many files at
once.

Both a **desktop GUI** (dark mode, page thumbnails, recent files) and a full
**command-line interface** are included.

## Not included (and why)

To stay 100% open source and permissively licensed, features that require
proprietary engines or non-permissive code are intentionally left out:

- **High-fidelity PDF → Word / Excel / PowerPoint** and **Office → PDF** — good
  results need proprietary engines (or a heavyweight LibreOffice dependency). We
  ship PDF → Text and PDF → Images instead.
- **Editing existing text in place** — no reliable open-source engine exists.
- **AI features** (summarize, chat with PDF, Q&A, auto-categorize) — require an
  external LLM service.
- **Cloud integrations** (Google Drive / OneDrive / Dropbox) — proprietary SDKs.
- **Certificate-based digital signature validation** — out of scope for v1.

These may return later if a permissive, offline path becomes practical.

## Install

Download **`PDFToolkit-Setup.exe`** from the
[QuickOpen page](https://quickopen.ai/projects/pdf-toolkit) or the
[GitHub release](https://github.com/quickpod/pdf-toolkit/releases/latest) and
double-click it. It installs per-user (no admin), adds Desktop and Start Menu
shortcuts, and can optionally trust the QuickOpen Root CA so Windows verifies our
signature. The installer is Authenticode-signed by the QuickOpen Code Signing CA;
verify it against [quickopen.ai/trust](https://quickopen.ai/trust).

## Run from source

```sh
pip install -r requirements.txt
python pdf_toolkit_app.py          # GUI
python -m pdftoolkit --help        # CLI
```

### CLI examples

```sh
python -m pdftoolkit merge a.pdf b.pdf -o out.pdf
python -m pdftoolkit split in.pdf -d out/ --ranges 1-3 4-6
python -m pdftoolkit rotate in.pdf 90 -o out.pdf -p 1-2
python -m pdftoolkit compress in.pdf -o small.pdf --level high
python -m pdftoolkit images2pdf *.png -o out.pdf
python -m pdftoolkit pdf2images in.pdf -d imgs/ --dpi 150 --fmt png
python -m pdftoolkit protect in.pdf -o enc.pdf --user-password secret
python -m pdftoolkit watermark in.pdf "CONFIDENTIAL" -o wm.pdf --position tiled
```

See [`pdftoolkit/README-API.md`](pdftoolkit/README-API.md) for the full library
API, and run any subcommand with `--help` for its flags.

## Built with (all permissive / weak-copyleft — no AGPL, no proprietary)

[pypdf](https://pypi.org/project/pypdf/) (BSD) ·
[pikepdf](https://pypi.org/project/pikepdf/) / qpdf (MPL-2.0 / Apache-2.0) ·
[pypdfium2](https://pypi.org/project/pypdfium2/) (BSD / Apache-2.0) ·
[Pillow](https://pypi.org/project/Pillow/) (HPND) ·
[reportlab](https://pypi.org/project/reportlab/) (BSD).

We deliberately avoid PyMuPDF and Ghostscript (AGPL) to keep this project
permissively licensed.

## License

Apache-2.0 — see [LICENSE](LICENSE). This is a 100% AI-built project published on
QuickOpen.
