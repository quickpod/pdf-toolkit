# pdftoolkit — Public API Reference

A permissively-licensed (Apache-2.0) PDF utilities library. A GUI is expected to
be built on top of this package, so the API is deliberately small and explicit.

## Conventions

- **Page numbers are 1-based** in every public function (converted to 0-based
  internally).
- **Page ranges** are strings like `"1-3,5,8-10"` — see `parse_pages`. Ranges may
  be descending (`"3-1"`), order is preserved, and an empty/`None` spec means
  "all pages".
- Every function takes **explicit input/output paths**.
- On any failure a function raises **`PdfToolkitError`** (and only that). It never
  leaks a library-specific exception.
- Import from the top level: `from pdftoolkit import merge, compress, ...`.

```python
from pdftoolkit import PdfToolkitError, merge, compress
```

---

## errors

- `class PdfToolkitError(Exception)` — the single error type raised by all
  operations.

## pages_util

- `parse_pages(spec, total) -> list[int]`
  Parse `"1-3,5"` into 1-based page numbers, validated against `total`. `None`/`""`
  → `[1..total]`. Preserves order and duplicates. Raises on malformed/out-of-range.
- `to_zero_based(pages) -> list[int]` — subtract 1 from each.
- `unique_sorted(pages) -> list[int]` — sorted set.

## merge

- `merge(inputs: list[str], output: str) -> int`
  Concatenate PDFs. Returns total page count.

## split

- `split_pages(input, out_dir, prefix=None) -> list[str]`
  One file per page (`<prefix|stem>_page_<n>.pdf`). Returns output paths.
- `split_ranges(input, ranges: list[str], out_dir) -> list[str]`
  One file per range spec (`<stem>_<idx>.pdf`). Returns output paths.
- `split_every(input, n, out_dir) -> list[str]`
  Chunks of `n` pages (`<stem>_part_<k>.pdf`). Returns output paths.

## pages

- `extract(input, output, pages_spec) -> int`
  Keep only `pages_spec` (order preserved). Returns page count written.
- `delete(input, output, pages_spec) -> int`
  Remove `pages_spec`. Returns page count written. Raises if all pages removed.
- `rotate(input, output, degrees, pages_spec=None) -> int`
  Rotate by `degrees` (multiple of 90, may be negative). `pages_spec=None` → all.
  Cumulative with existing rotation. Returns page count.
- `reorder(input, output, order: list[int]) -> int`
  `order` must be a permutation of `1..total`. Returns page count.
- `duplicate(input, output, pages_spec) -> int`
  Each selected page emitted twice, in place. Returns page count written.

## compress

- `compress(input, output, level='medium') -> dict`
  `level` ∈ `{'low','medium','high'}` (low = least aggressive). Downscales/
  recompresses image XObjects (best-effort per image), regenerates object
  streams, drops unreferenced objects. Guaranteed valid and never larger than
  the input (falls back to copying the original if processing would grow it).
  Returns `{'original_size', 'new_size', 'ratio', 'level'}` (`ratio` = fraction
  saved, 0..1).

## optimize

- `web_optimize(input, output) -> str`
  Linearize ("fast web view"). Returns `output`.
- `remove_metadata(input, output) -> str`
  Strip `/Info` dict and XMP metadata. Returns `output`.

## convert

- `images_to_pdf(images: list[str], output, page_size=None) -> int`
  Combine images (PNG/JPG/BMP/TIFF), order preserved, EXIF auto-orient,
  transparency flattened to white. `page_size` = `(w,h)` points or `"A4"`/
  `"letter"`/`"legal"` (image centred & scaled to fit); `None` = page per image
  at 72 dpi. Returns page count.
- `pdf_to_images(input, out_dir, fmt='png', dpi=150, pages_spec=None) -> list[str]`
  Render pages with PDFium. Returns image paths.
- `pdf_to_text(input, output=None, pages_spec=None) -> str`
  Extract text (pypdf). Writes to `output` if given; always returns the text.
- `extract_images(input, out_dir) -> list[str]`
  Save embedded raster images. Returns written paths.

## security

- `protect(input, output, user_password='', owner_password=None, allow_print=True, allow_copy=True, allow_modify=True, allow_annotate=True) -> str`
  AES-256 (PDF 2.0, R=6). `owner_password` defaults to `user_password`. Returns
  `output`.
- `unprotect(input, output, password) -> str`
  Decrypt. Raises `PdfToolkitError("incorrect password")` on bad password.
- `is_encrypted(input) -> bool`
  True if encrypted (no password needed to check).

## watermark

- `text_watermark(input, output, text, opacity=0.3, position='center', rotation=45, font_size=48, color=(128,128,128), pages_spec=None) -> int`
  Stamp text. `position` ∈ `center | top-left | top-right | bottom-left |
  bottom-right | top-center | bottom-center | tiled`. Returns page count.
- `image_watermark(input, output, image_path, opacity=0.3, position='center', scale=0.5, pages_spec=None) -> int`
  Stamp an image (`scale` × page width, aspect preserved, opacity via soft mask).
  Same positions (incl. `tiled`). Returns page count.

## stamp

- `add_page_numbers(input, output, position='bottom-center', start=1, fmt='{n}') -> int`
  `fmt` supports `{n}` (page number) and `{total}`. Returns page count.
- `add_header_footer(input, output, header=None, footer=None) -> int`
  Centred header (top) / footer (bottom). At least one required. Returns page count.

## metadata

- `get_metadata(input) -> dict`
  Keys: `title, author, subject, keywords, creator, producer, creation_date,
  mod_date` (missing → `None`).
- `set_metadata(input, output, title=None, author=None, subject=None, keywords=None) -> str`
  Only non-`None` fields applied; existing fields preserved. Returns `output`.
- `info(input) -> dict`
  `{'path', 'file_size', 'page_count', 'encrypted', 'page_sizes', 'metadata'}`.
  `page_sizes` = list of `(w,h)` in points. For an encrypted file, `page_count`
  is `None` and `page_sizes` is empty (cannot inspect without the password).

## bookmarks

- `add_bookmark(input, output, title, page, parent=None) -> outline_item`
  Add one bookmark → `page` (1-based). `parent` = an item returned by a previous
  call (to nest) or `None`. Returns the created item. (Rewrites the file, so chain
  calls via the previous output; use `generate_toc` to build many at once.)
- `list_bookmarks(input) -> list[dict]`
  Flat list of `{'title', 'page', 'level'}` (page 1-based or `None`).
- `generate_toc(input, output, entries) -> int`
  `entries` = list of `(title, page)`. Builds a flat outline. Returns count.

## redact

- `redact_rects(input, output, page, rects) -> int`
  Cover `rects` (list of `(x0,y0,x1,y1)` in points, origin bottom-left) on `page`
  (1-based) with opaque black boxes and flatten. Returns rectangle count.
  **Limitation (honest):** this hides content *visually* but underlying text is
  not guaranteed removed from the content stream. For high-assurance redaction,
  rasterise the page (`pdf_to_images`) and rebuild — see the module docstring.

## compare

- `compare_text(a, b) -> dict`
  Positional per-page text diff (difflib). Returns `{'pages': [{'page','added',
  'removed','changed'}...], 'total_added', 'total_removed', 'identical'}`.

## repair

- `repair(input, output) -> str`
  Re-save via qpdf recovery (rebuilds xref/structure where possible). Returns
  `output`.

## batch

- `batch_apply(func, inputs, out_dir, suffix='', ext=None, **kwargs) -> list[dict]`
  Call `func(input, output, **kwargs)` per input; output =
  `<out_dir>/<stem><suffix><ext>`. Returns `[{'input','output','result'}, ...]`.
- `batch_compress(inputs, out_dir, level='medium') -> list[dict]`
- `batch_watermark(inputs, out_dir, text, **kwargs) -> list[dict]`
- `batch_convert_to_images(inputs, out_dir, fmt='png', dpi=150) -> list[dict]`
  Renders each input under `<out_dir>/<stem>/`; returns
  `[{'input','out_dir','images'}, ...]`.

---

## CLI

Every function is exposed via `python -m pdftoolkit <command>`. Run
`python -m pdftoolkit <command> --help` for options. Commands: `merge, split,
extract, delete, rotate, reorder, duplicate, compress, optimize,
remove-metadata, images2pdf, pdf2images, pdf2text, extract-images, protect,
unprotect, info, metadata, watermark, page-numbers, header-footer, redact,
compare, repair, bookmarks, batch-compress, batch-watermark, batch-images`.

The CLI exits non-zero with a clean `error: <message>` (no traceback) on
`PdfToolkitError`.

## Dependencies & licenses

All permissive / weak-copyleft (no AGPL, no proprietary):

| Package     | License                | Role                                        |
|-------------|------------------------|---------------------------------------------|
| pypdf       | BSD-3-Clause           | merge/split/pages/metadata/bookmarks/text   |
| pikepdf     | MPL-2.0 (qpdf Apache)  | compress/optimize/repair/AES-256 encryption |
| pypdfium2   | BSD-3-Clause / Apache  | PDF → images rendering                      |
| Pillow      | HPND (MIT-style)       | image I/O, images → PDF                      |
| reportlab   | BSD                    | overlays: watermark/stamp/page numbers      |
