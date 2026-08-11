"""Command-line interface: ``python -m pdftoolkit <command> ...``."""

from __future__ import annotations

import argparse
import sys

from . import (
    PdfToolkitError,
    add_header_footer,
    add_page_numbers,
    compare_text,
    compress,
    delete,
    duplicate,
    extract,
    extract_images,
    get_metadata,
    images_to_pdf,
    info,
    is_encrypted,
    list_bookmarks,
    merge,
    pdf_to_images,
    pdf_to_text,
    protect,
    redact_rects,
    remove_metadata,
    reorder,
    repair,
    rotate,
    set_metadata,
    split_every,
    split_pages,
    split_ranges,
    text_watermark,
    unprotect,
    web_optimize,
)
from .batch import batch_compress, batch_convert_to_images, batch_watermark
from .common import human_size


def _pct(ratio):
    return f"{ratio * 100:.0f}%"


# --- command handlers -------------------------------------------------------


def cmd_merge(a):
    n = merge(a.inputs, a.output)
    print(f"Merged {len(a.inputs)} files -> {a.output} ({n} pages)")


def cmd_split(a):
    if a.every:
        outs = split_every(a.input, a.every, a.out_dir)
    elif a.ranges:
        outs = split_ranges(a.input, a.ranges, a.out_dir)
    else:
        outs = split_pages(a.input, a.out_dir, prefix=a.prefix)
    print(f"Split {a.input} -> {len(outs)} files in {a.out_dir}")


def cmd_extract(a):
    n = extract(a.input, a.output, a.pages)
    print(f"Extracted {n} pages -> {a.output}")


def cmd_delete(a):
    n = delete(a.input, a.output, a.pages)
    print(f"Deleted pages {a.pages}; {n} pages remain -> {a.output}")


def cmd_rotate(a):
    n = rotate(a.input, a.output, a.degrees, a.pages)
    print(f"Rotated {a.degrees} deg -> {a.output} ({n} pages)")


def cmd_reorder(a):
    order = [int(x) for x in a.order.split(",")]
    n = reorder(a.input, a.output, order)
    print(f"Reordered {n} pages -> {a.output}")


def cmd_duplicate(a):
    n = duplicate(a.input, a.output, a.pages)
    print(f"Duplicated pages {a.pages}; {n} pages total -> {a.output}")


def cmd_compress(a):
    r = compress(a.input, a.output, level=a.level)
    print(
        f"Compressed {human_size(r['original_size'])} -> "
        f"{human_size(r['new_size'])} ({_pct(r['ratio'])} smaller) -> {a.output}"
    )


def cmd_optimize(a):
    web_optimize(a.input, a.output)
    print(f"Web-optimized (linearized) -> {a.output}")


def cmd_remove_metadata(a):
    remove_metadata(a.input, a.output)
    print(f"Removed metadata -> {a.output}")


def cmd_images2pdf(a):
    n = images_to_pdf(a.images, a.output, page_size=a.page_size)
    print(f"Combined {n} images -> {a.output}")


def cmd_pdf2images(a):
    outs = pdf_to_images(a.input, a.out_dir, fmt=a.fmt, dpi=a.dpi, pages_spec=a.pages)
    print(f"Rendered {len(outs)} pages -> {a.out_dir} ({a.fmt}, {a.dpi} dpi)")


def cmd_pdf2text(a):
    text = pdf_to_text(a.input, a.output, pages_spec=a.pages)
    if a.output:
        print(f"Extracted text -> {a.output} ({len(text)} chars)")
    else:
        sys.stdout.write(text + "\n")


def cmd_extract_images(a):
    outs = extract_images(a.input, a.out_dir)
    print(f"Extracted {len(outs)} embedded images -> {a.out_dir}")


def cmd_protect(a):
    protect(
        a.input,
        a.output,
        user_password=a.user_password,
        owner_password=a.owner_password,
        allow_print=not a.no_print,
        allow_copy=not a.no_copy,
        allow_modify=not a.no_modify,
        allow_annotate=not a.no_annotate,
    )
    print(f"Encrypted (AES-256) -> {a.output}")


def cmd_unprotect(a):
    unprotect(a.input, a.output, a.password)
    print(f"Decrypted -> {a.output}")


def cmd_info(a):
    d = info(a.input)
    print(f"File:      {d['path']}")
    print(f"Size:      {human_size(d['file_size']) if d['file_size'] else 'n/a'}")
    print(f"Pages:     {d['page_count'] if d['page_count'] is not None else '(encrypted)'}")
    print(f"Encrypted: {d['encrypted']}")
    if d["page_sizes"]:
        first = d["page_sizes"][0]
        print(f"Page size: {first[0]} x {first[1]} pt (page 1)")
    meta = d["metadata"]
    for key in ("title", "author", "subject"):
        if meta.get(key):
            print(f"{key.capitalize():<10} {meta[key]}")


def cmd_metadata(a):
    if a.set:
        set_metadata(
            a.input,
            a.output,
            title=a.title,
            author=a.author,
            subject=a.subject,
            keywords=a.keywords,
        )
        print(f"Updated metadata -> {a.output}")
    else:
        meta = get_metadata(a.input)
        for key, value in meta.items():
            print(f"{key:<14} {value if value is not None else ''}")


def cmd_watermark(a):
    n = text_watermark(
        a.input,
        a.output,
        a.text,
        opacity=a.opacity,
        position=a.position,
        rotation=a.rotation,
        font_size=a.font_size,
        pages_spec=a.pages,
    )
    print(f"Watermarked {n} pages -> {a.output}")


def cmd_page_numbers(a):
    n = add_page_numbers(a.input, a.output, position=a.position, start=a.start, fmt=a.fmt)
    print(f"Added page numbers to {n} pages -> {a.output}")


def cmd_header_footer(a):
    n = add_header_footer(a.input, a.output, header=a.header, footer=a.footer)
    print(f"Added header/footer to {n} pages -> {a.output}")


def cmd_redact(a):
    rects = []
    for r in a.rect:
        vals = [float(x) for x in r.split(",")]
        if len(vals) != 4:
            raise PdfToolkitError("each --rect needs 4 comma-separated numbers x0,y0,x1,y1")
        rects.append(tuple(vals))
    n = redact_rects(a.input, a.output, a.page, rects)
    print(f"Redacted {n} rectangles on page {a.page} -> {a.output}")


def cmd_compare(a):
    d = compare_text(a.a, a.b)
    if d["identical"]:
        print("Documents have identical text.")
    else:
        print(f"+{d['total_added']} / -{d['total_removed']} lines across pages")
        for p in d["pages"]:
            if p["changed"]:
                print(f"  page {p['page']}: +{p['added']} -{p['removed']}")


def cmd_repair(a):
    repair(a.input, a.output)
    print(f"Repaired -> {a.output}")


def cmd_bookmarks(a):
    items = list_bookmarks(a.input)
    if not items:
        print("No bookmarks.")
    for it in items:
        indent = "  " * it["level"]
        print(f"{indent}- {it['title']} (page {it['page']})")


def cmd_batch_compress(a):
    res = batch_compress(a.inputs, a.out_dir, level=a.level)
    print(f"Compressed {len(res)} files -> {a.out_dir}")


def cmd_batch_watermark(a):
    res = batch_watermark(a.inputs, a.out_dir, a.text)
    print(f"Watermarked {len(res)} files -> {a.out_dir}")


def cmd_batch_images(a):
    res = batch_convert_to_images(a.inputs, a.out_dir, fmt=a.fmt, dpi=a.dpi)
    total = sum(len(r["images"]) for r in res)
    print(f"Rendered {total} pages from {len(res)} files -> {a.out_dir}")


# --- parser -----------------------------------------------------------------


def build_parser():
    p = argparse.ArgumentParser(
        prog="pdftoolkit",
        description="Permissively-licensed PDF utilities. Pages are 1-based; "
        "ranges look like '1-3,5,8-10'.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, help, handler):
        sp = sub.add_parser(name, help=help)
        sp.set_defaults(func=handler)
        return sp

    s = add("merge", "Concatenate PDFs", cmd_merge)
    s.add_argument("inputs", nargs="+")
    s.add_argument("-o", "--output", required=True)

    s = add("split", "Split a PDF into files", cmd_split)
    s.add_argument("input")
    s.add_argument("-d", "--out-dir", required=True)
    s.add_argument("--every", type=int, help="chunk every N pages")
    s.add_argument("--ranges", nargs="+", help="one file per range, e.g. 1-3 4-6")
    s.add_argument("--prefix", help="filename prefix (one-file-per-page mode)")

    s = add("extract", "Keep only selected pages", cmd_extract)
    s.add_argument("input")
    s.add_argument("pages")
    s.add_argument("-o", "--output", required=True)

    s = add("delete", "Remove selected pages", cmd_delete)
    s.add_argument("input")
    s.add_argument("pages")
    s.add_argument("-o", "--output", required=True)

    s = add("rotate", "Rotate pages", cmd_rotate)
    s.add_argument("input")
    s.add_argument("degrees", type=int, help="multiple of 90")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("-p", "--pages", help="pages to rotate (default: all)")

    s = add("reorder", "Rearrange pages", cmd_reorder)
    s.add_argument("input")
    s.add_argument("order", help="comma-separated permutation, e.g. 3,1,2")
    s.add_argument("-o", "--output", required=True)

    s = add("duplicate", "Duplicate selected pages", cmd_duplicate)
    s.add_argument("input")
    s.add_argument("pages")
    s.add_argument("-o", "--output", required=True)

    s = add("compress", "Compress/optimize a PDF", cmd_compress)
    s.add_argument("input")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("-l", "--level", choices=["low", "medium", "high"], default="medium")

    s = add("optimize", "Linearize for fast web view", cmd_optimize)
    s.add_argument("input")
    s.add_argument("-o", "--output", required=True)

    s = add("remove-metadata", "Strip document metadata", cmd_remove_metadata)
    s.add_argument("input")
    s.add_argument("-o", "--output", required=True)

    s = add("images2pdf", "Combine images into a PDF", cmd_images2pdf)
    s.add_argument("images", nargs="+")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--page-size", help="A4, letter, legal (default: image size)")

    s = add("pdf2images", "Render pages to images", cmd_pdf2images)
    s.add_argument("input")
    s.add_argument("-d", "--out-dir", required=True)
    s.add_argument("--fmt", default="png")
    s.add_argument("--dpi", type=int, default=150)
    s.add_argument("-p", "--pages", help="pages to render (default: all)")

    s = add("pdf2text", "Extract text", cmd_pdf2text)
    s.add_argument("input")
    s.add_argument("-o", "--output", help="write to file (default: stdout)")
    s.add_argument("-p", "--pages")

    s = add("extract-images", "Pull embedded images", cmd_extract_images)
    s.add_argument("input")
    s.add_argument("-d", "--out-dir", required=True)

    s = add("protect", "Encrypt with AES-256", cmd_protect)
    s.add_argument("input")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--user-password", default="")
    s.add_argument("--owner-password", default=None)
    s.add_argument("--no-print", action="store_true")
    s.add_argument("--no-copy", action="store_true")
    s.add_argument("--no-modify", action="store_true")
    s.add_argument("--no-annotate", action="store_true")

    s = add("unprotect", "Decrypt", cmd_unprotect)
    s.add_argument("input")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--password", required=True)

    s = add("info", "Show document summary", cmd_info)
    s.add_argument("input")

    s = add("metadata", "Get or set metadata", cmd_metadata)
    s.add_argument("input")
    s.add_argument("--set", action="store_true", help="set mode (requires -o)")
    s.add_argument("-o", "--output")
    s.add_argument("--title")
    s.add_argument("--author")
    s.add_argument("--subject")
    s.add_argument("--keywords")

    s = add("watermark", "Add a text watermark", cmd_watermark)
    s.add_argument("input")
    s.add_argument("text")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--opacity", type=float, default=0.3)
    s.add_argument("--position", default="center")
    s.add_argument("--rotation", type=float, default=45)
    s.add_argument("--font-size", type=int, default=48)
    s.add_argument("-p", "--pages")

    s = add("page-numbers", "Stamp page numbers", cmd_page_numbers)
    s.add_argument("input")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--position", default="bottom-center")
    s.add_argument("--start", type=int, default=1)
    s.add_argument("--fmt", default="{n}")

    s = add("header-footer", "Add header/footer text", cmd_header_footer)
    s.add_argument("input")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--header")
    s.add_argument("--footer")

    s = add("redact", "Cover rectangles with black boxes", cmd_redact)
    s.add_argument("input")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--page", type=int, required=True)
    s.add_argument("--rect", action="append", required=True, help="x0,y0,x1,y1 (repeatable)")

    s = add("compare", "Diff text of two PDFs", cmd_compare)
    s.add_argument("a")
    s.add_argument("b")

    s = add("repair", "Repair a damaged PDF", cmd_repair)
    s.add_argument("input")
    s.add_argument("-o", "--output", required=True)

    s = add("bookmarks", "List bookmarks", cmd_bookmarks)
    s.add_argument("input")

    s = add("batch-compress", "Compress many PDFs", cmd_batch_compress)
    s.add_argument("inputs", nargs="+")
    s.add_argument("-d", "--out-dir", required=True)
    s.add_argument("-l", "--level", choices=["low", "medium", "high"], default="medium")

    s = add("batch-watermark", "Watermark many PDFs", cmd_batch_watermark)
    s.add_argument("inputs", nargs="+")
    s.add_argument("-d", "--out-dir", required=True)
    s.add_argument("--text", required=True)

    s = add("batch-images", "Render many PDFs to images", cmd_batch_images)
    s.add_argument("inputs", nargs="+")
    s.add_argument("-d", "--out-dir", required=True)
    s.add_argument("--fmt", default="png")
    s.add_argument("--dpi", type=int, default=150)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except PdfToolkitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
