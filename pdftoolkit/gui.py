#!/usr/bin/env python3
r"""PDF Toolkit -- a pure-stdlib tkinter GUI on top of the ``pdftoolkit`` API.

A single main window: a left sidebar of tool categories (Organize, Convert,
Optimize, Security, Watermark, Pages/Meta, Advanced, Batch) and a main panel
that swaps to the selected tool.  Every operation calls the tested core library
(never re-implements PDF logic) and runs on a background thread so the UI stays
responsive; results are marshalled back with ``self.after`` and reported in a
clear inline area -- an output path plus an "Open folder" button on success, or
the ``PdfToolkitError`` message (never a raw traceback) on failure.

Design goals baked in here:
  * pure standard-library tkinter/ttk -- NO third-party GUI deps.  Dark mode is
    a ttk-style + palette swap; "drag and drop" is an explicit "Add files..."
    button (real OS DnD needs a dependency we deliberately avoid).
  * Importing this module does nothing.  Only :func:`main` builds a root window,
    and it degrades gracefully (prints a message, returns) with no display.
  * Frozen-exe safe: bundled assets are resolved via ``sys._MEIPASS`` / the exe
    directory when ``sys.frozen`` is set -- never ``__file__``.

100% AI-built, open source, published on QuickOpen (quickopen.ai).
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading

# NOTE: tkinter is imported lazily inside main()/build so that merely importing
# this module (e.g. during packaging or on a headless CI box) never fails.

APP_NAME = "PDF Toolkit"
APP_VERSION = "1.0.0"
WINDOW_TITLE = "PDF Toolkit — by QuickOpen (quickopen.ai)"
PROJECT_URL = "https://quickopen.ai"

PDF_TYPES = [("PDF files", "*.pdf"), ("All files", "*.*")]
IMAGE_TYPES = [
    ("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif"),
    ("All files", "*.*"),
]

# Named anchor positions understood by the core (see common.position_point).
POSITIONS = [
    "center", "top-left", "top-right", "bottom-left",
    "bottom-right", "top-center", "bottom-center",
]
WM_POSITIONS = POSITIONS + ["tiled"]

# ---- colour palettes (mirror the QuickOpen palette) -------------------------
PALETTES = {
    "light": {
        "bg": "#f5f7fa", "surface": "#ffffff", "text": "#141820",
        "muted": "#5b6472", "primary": "#2f5fe0", "primary_hi": "#2450c8",
        "entry": "#ffffff", "border": "#d5dae2", "sel": "#2f5fe0",
        "sel_fg": "#ffffff", "trough": "#e2e7ef", "ok": "#1f7a3d",
        "err": "#c0392b",
    },
    "dark": {
        "bg": "#0f1115", "surface": "#1a1e24", "text": "#f1f3f7",
        "muted": "#9aa4b2", "primary": "#5b86f7", "primary_hi": "#7098ff",
        "entry": "#1a1e24", "border": "#2a2f38", "sel": "#5b86f7",
        "sel_fg": "#0f1115", "trough": "#2a2f38", "ok": "#5bd68a",
        "err": "#ff6b5e",
    },
}

# (category, [(tool_id, label), ...]) -- tool_id maps to a _panel_<id> method.
TOOL_TREE = [
    ("Organize", [
        ("merge", "Merge"),
        ("split", "Split"),
        ("extract", "Extract pages"),
        ("delete", "Delete pages"),
        ("rotate", "Rotate"),
        ("reorder", "Reorder pages"),
        ("duplicate", "Duplicate pages"),
    ]),
    ("Convert", [
        ("images2pdf", "Images → PDF"),
        ("pdf2images", "PDF → Images"),
        ("pdf2text", "PDF → Text"),
        ("extractimages", "Extract images"),
    ]),
    ("Optimize", [
        ("compress", "Compress"),
        ("weboptimize", "Web-optimize"),
        ("removemeta", "Remove metadata"),
    ]),
    ("Security", [
        ("protect", "Protect"),
        ("unprotect", "Unprotect"),
        ("encstatus", "Encryption status"),
    ]),
    ("Watermark", [
        ("textwm", "Text watermark"),
        ("imagewm", "Image watermark"),
    ]),
    ("Pages/Meta", [
        ("pagenumbers", "Page numbers"),
        ("headerfooter", "Header / Footer"),
        ("metadata", "Metadata editor"),
        ("bookmarks", "Bookmarks"),
        ("info", "Info panel"),
    ]),
    ("Advanced", [
        ("redact", "Redact"),
        ("compare", "Compare"),
        ("repair", "Repair"),
    ]),
    ("Batch", [
        ("batchcompress", "Batch compress"),
        ("batchwatermark", "Batch watermark"),
        ("batchimages", "Batch → images"),
    ]),
]


# ---------------------------------------------------------------------------
# Asset / frozen handling
# ---------------------------------------------------------------------------
def asset_path(name):
    """Locate a bundled asset from source OR a PyInstaller one-file build.

    For a frozen exe we look only at ``sys._MEIPASS`` and the executable's own
    directory (never ``__file__``, which points inside the temp unpack dir in a
    way that is unreliable for sibling assets).  From source we also consult the
    package dir, the repo root and the CWD.  Returns an absolute path or ``None``.
    """
    roots = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(meipass)
        roots.append(os.path.dirname(os.path.abspath(sys.executable)))
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        roots += [here, os.path.dirname(here), os.getcwd()]
    for root in roots:
        candidate = os.path.join(root, name)
        if os.path.exists(candidate):
            return candidate
    return None


def human_size(num_bytes):
    """Human-readable byte size (re-uses the core helper when available)."""
    try:
        from .common import human_size as _hs
        return _hs(num_bytes)
    except Exception:
        size = float(num_bytes or 0)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024.0 or unit == "TB":
                return f"{int(size)}{unit}" if unit == "B" else f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"


def open_in_file_manager(path):
    """Best-effort 'reveal in file manager', guarded on every platform."""
    try:
        folder = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
        if hasattr(os, "startfile"):          # Windows
            os.startfile(folder)              # noqa: S606 - intended
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", folder])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", folder])
        return True
    except Exception:
        return False


def open_with_default_app(path):
    """Open a file with the OS default application, guarded."""
    try:
        if hasattr(os, "startfile"):
            os.startfile(path)                # noqa: S606
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", path])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# The app (built lazily; tkinter imported only inside build_app/main)
# ---------------------------------------------------------------------------
def build_app():
    """Construct and return the App class bound to a live tkinter import.

    Kept inside a function so this module imports cleanly without a display.
    """
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    from . import guiconfig
    from .errors import PdfToolkitError
    from . import (
        merge, split_pages, split_ranges, split_every,
        extract, delete, rotate, reorder, duplicate,
        compress, web_optimize, remove_metadata,
        images_to_pdf, pdf_to_images, pdf_to_text, extract_images,
        protect, unprotect, is_encrypted,
        text_watermark, image_watermark,
        add_page_numbers, add_header_footer,
        get_metadata, set_metadata, info,
        list_bookmarks, generate_toc,
        redact_rects, compare_text, repair,
        batch_compress, batch_watermark, batch_convert_to_images,
    )

    FONT = "Segoe UI"

    # -- small reusable widgets ------------------------------------------

    class FileRow(ttk.Frame):
        """A labelled path field + Browse button. ``mode`` picks the dialog."""

        def __init__(self, master, app, label, mode="open_pdf",
                     filetypes=None, on_change=None):
            super().__init__(master, style="TFrame")
            self.app = app
            self.mode = mode
            self.filetypes = filetypes
            self.on_change = on_change
            self.var = tk.StringVar()
            ttk.Label(self, text=label, width=14, anchor="w").pack(side="left")
            ent = ttk.Entry(self, textvariable=self.var)
            ent.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ttk.Button(self, text="Browse…", command=self._browse,
                       width=10).pack(side="left")
            if on_change:
                self.var.trace_add("write", lambda *_: on_change(self.var.get()))

        def _browse(self):
            ft = self.filetypes or PDF_TYPES
            if self.mode == "dir":
                p = filedialog.askdirectory(title="Choose a folder")
            elif self.mode == "save_pdf":
                p = filedialog.asksaveasfilename(
                    title="Save as", defaultextension=".pdf", filetypes=ft)
            elif self.mode == "save_any":
                p = filedialog.asksaveasfilename(title="Save as", filetypes=ft)
            elif self.mode == "open_any":
                p = filedialog.askopenfilename(title="Choose a file", filetypes=ft)
            else:
                p = filedialog.askopenfilename(title="Choose a PDF", filetypes=ft)
            if p:
                self.var.set(p)

        def get(self):
            return self.var.get().strip()

        def set(self, value):
            self.var.set(value or "")

    class FileList(ttk.Frame):
        """A multi-file listbox with Add / Remove / Up / Down (+ a DnD note)."""

        def __init__(self, master, app, filetypes=None, note=True):
            super().__init__(master, style="TFrame")
            self.app = app
            self.filetypes = filetypes or PDF_TYPES
            box = ttk.Frame(self, style="TFrame")
            box.pack(fill="both", expand=True)
            self.listbox = tk.Listbox(box, height=8, activestyle="none",
                                      selectmode="extended", exportselection=False)
            sb = ttk.Scrollbar(box, orient="vertical", command=self.listbox.yview)
            self.listbox.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            self.listbox.pack(side="left", fill="both", expand=True)
            app.track(self.listbox, "listbox")

            btns = ttk.Frame(self, style="TFrame")
            btns.pack(fill="x", pady=(6, 0))
            ttk.Button(btns, text="Add files…", command=self.add,
                       style="Accent.TButton").pack(side="left")
            ttk.Button(btns, text="Remove", command=self.remove).pack(side="left", padx=4)
            ttk.Button(btns, text="Up", command=lambda: self.move(-1),
                       width=4).pack(side="left")
            ttk.Button(btns, text="Down", command=lambda: self.move(1),
                       width=5).pack(side="left", padx=(4, 0))
            ttk.Button(btns, text="Clear", command=self.clear).pack(side="left", padx=4)
            if note:
                ttk.Label(self, style="Muted.TLabel", wraplength=520, justify="left",
                          text="Tip: use “Add files…”. OS drag-and-drop isn’t "
                               "available (it would require a third-party "
                               "dependency this app avoids).").pack(
                    anchor="w", pady=(4, 0))

        def add(self):
            paths = filedialog.askopenfilenames(title="Add files",
                                                filetypes=self.filetypes)
            for p in paths:
                self.listbox.insert("end", p)
            if paths:
                self.app.remember_input(paths[0])

        def remove(self):
            for i in reversed(self.listbox.curselection()):
                self.listbox.delete(i)

        def move(self, delta):
            sel = list(self.listbox.curselection())
            if not sel:
                return
            items = list(self.listbox.get(0, "end"))
            order = range(len(sel)) if delta < 0 else range(len(sel) - 1, -1, -1)
            new_sel = []
            for k in order:
                i = sel[k]
                j = i + delta
                if j < 0 or j >= len(items):
                    new_sel.append(i)
                    continue
                items[i], items[j] = items[j], items[i]
                new_sel.append(j)
            self.listbox.delete(0, "end")
            for it in items:
                self.listbox.insert("end", it)
            self.listbox.selection_clear(0, "end")
            for j in new_sel:
                self.listbox.selection_set(j)

        def clear(self):
            self.listbox.delete(0, "end")

        def items(self):
            return list(self.listbox.get(0, "end"))

    # -- the main window --------------------------------------------------

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title(WINDOW_TITLE)
            self.geometry("1080x680")
            self.minsize(880, 560)

            self.theme = guiconfig.get_theme()
            self._busy = False
            self._panels = {}          # tool_id -> built frame (lazy)
            self._current = None
            self._tracked = []         # (tk_widget, role) for manual re-theming
            self._img_refs = []        # keep PhotoImage refs alive
            self._history = []         # session output paths
            self._last_output_dir = None
            self._tmpdir = tempfile.mkdtemp(prefix="pdftk_gui_")

            self._set_icon()
            self._build_menu()
            self._build_layout()
            self._apply_theme()
            self.protocol("WM_DELETE_WINDOW", self._on_close)
            # open the first tool by default
            self.after(50, lambda: self._select_first_tool())

        # ---- assets / icon
        def _set_icon(self):
            try:
                ico = asset_path("pdf-toolkit.ico")
                if ico:
                    self.iconbitmap(ico)
                    return
            except Exception:
                pass
            try:
                png = asset_path("pdf-toolkit.png")
                if png:
                    img = tk.PhotoImage(file=png)
                    self._img_refs.append(img)
                    self.iconphoto(True, img)
            except Exception:
                pass  # icon is cosmetic; never block launch

        # ---- theming
        def track(self, widget, role):
            self._tracked.append((widget, role))

        def _pal(self):
            return PALETTES[self.theme]

        def _apply_theme(self):
            p = self._pal()
            style = ttk.Style(self)
            try:
                style.theme_use("clam")
            except Exception:
                pass
            self.configure(bg=p["bg"])
            style.configure(".", background=p["bg"], foreground=p["text"],
                            fieldbackground=p["entry"], bordercolor=p["border"],
                            font=(FONT, 10))
            style.configure("TFrame", background=p["bg"])
            style.configure("Sidebar.TFrame", background=p["surface"])
            style.configure("Card.TFrame", background=p["surface"])
            style.configure("TLabel", background=p["bg"], foreground=p["text"])
            style.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"])
            style.configure("Header.TLabel", background=p["bg"], foreground=p["text"],
                            font=(FONT, 15, "bold"))
            style.configure("Sub.TLabel", background=p["bg"], foreground=p["muted"],
                            font=(FONT, 10))
            style.configure("Brand.TLabel", background=p["surface"],
                            foreground=p["text"], font=(FONT, 12, "bold"))
            style.configure("Ok.TLabel", background=p["bg"], foreground=p["ok"])
            style.configure("Err.TLabel", background=p["bg"], foreground=p["err"])
            style.configure("Status.TLabel", background=p["surface"],
                            foreground=p["muted"])
            style.configure("TButton", background=p["surface"], foreground=p["text"],
                            bordercolor=p["border"], focuscolor=p["surface"],
                            padding=(10, 5))
            style.map("TButton",
                      background=[("active", p["trough"]), ("disabled", p["bg"])],
                      foreground=[("disabled", p["muted"])])
            style.configure("Accent.TButton", background=p["primary"],
                            foreground="#ffffff", padding=(12, 6))
            style.map("Accent.TButton",
                      background=[("active", p["primary_hi"]),
                                  ("disabled", p["border"])],
                      foreground=[("disabled", p["muted"])])
            style.configure("Toggle.TButton", background=p["surface"],
                            foreground=p["text"], padding=(8, 4))
            for name in ("TEntry", "TSpinbox"):
                style.configure(name, fieldbackground=p["entry"], foreground=p["text"],
                                insertcolor=p["text"], bordercolor=p["border"])
            style.configure("TCombobox", fieldbackground=p["entry"],
                            foreground=p["text"], background=p["surface"],
                            arrowcolor=p["text"])
            style.map("TCombobox",
                      fieldbackground=[("readonly", p["entry"])],
                      foreground=[("readonly", p["text"])])
            style.configure("TCheckbutton", background=p["bg"], foreground=p["text"])
            style.map("TCheckbutton", background=[("active", p["bg"])])
            style.configure("TRadiobutton", background=p["bg"], foreground=p["text"])
            style.map("TRadiobutton", background=[("active", p["bg"])])
            style.configure("TLabelframe", background=p["bg"], foreground=p["text"],
                            bordercolor=p["border"])
            style.configure("TLabelframe.Label", background=p["bg"],
                            foreground=p["muted"])
            style.configure("Treeview", background=p["surface"],
                            fieldbackground=p["surface"], foreground=p["text"],
                            bordercolor=p["border"], rowheight=24)
            style.map("Treeview", background=[("selected", p["primary"])],
                      foreground=[("selected", p["sel_fg"])])
            style.configure("Sidebar.Treeview", background=p["surface"],
                            fieldbackground=p["surface"])
            style.configure("TScale", background=p["bg"], troughcolor=p["trough"])
            style.configure("Horizontal.TScale", background=p["bg"],
                            troughcolor=p["trough"])
            style.configure("TScrollbar", background=p["surface"],
                            troughcolor=p["bg"], bordercolor=p["border"],
                            arrowcolor=p["text"])
            style.configure("TSeparator", background=p["border"])

            # manually re-colour raw tk widgets (Listbox / Text / Canvas)
            for widget, role in list(self._tracked):
                try:
                    if role == "listbox":
                        widget.configure(bg=p["surface"], fg=p["text"],
                                         selectbackground=p["primary"],
                                         selectforeground=p["sel_fg"],
                                         highlightthickness=1,
                                         highlightbackground=p["border"],
                                         borderwidth=0)
                    elif role == "text":
                        widget.configure(bg=p["surface"], fg=p["text"],
                                         insertbackground=p["text"],
                                         selectbackground=p["primary"],
                                         selectforeground=p["sel_fg"],
                                         highlightthickness=1,
                                         highlightbackground=p["border"],
                                         borderwidth=0)
                    elif role == "canvas":
                        widget.configure(bg=p["surface"],
                                         highlightthickness=1,
                                         highlightbackground=p["border"])
                except Exception:
                    pass

        def toggle_theme(self):
            self.theme = "dark" if self.theme == "light" else "light"
            guiconfig.set_theme(self.theme)
            self._apply_theme()
            self._theme_btn.configure(
                text="☀ Light mode" if self.theme == "dark" else "🌙 Dark mode")

        # ---- menu
        def _build_menu(self):
            bar = tk.Menu(self)
            filem = tk.Menu(bar, tearoff=0)
            filem.add_command(label="Open…", accelerator="Ctrl+O",
                              command=self._open_file)
            self._recent_menu = tk.Menu(filem, tearoff=0)
            filem.add_cascade(label="Open Recent", menu=self._recent_menu)
            self._fill_recent_menu()
            filem.add_separator()
            filem.add_command(label="Session output history…",
                              command=self._show_history)
            filem.add_separator()
            filem.add_command(label="Exit", command=self._on_close)
            bar.add_cascade(label="File", menu=filem)

            viewm = tk.Menu(bar, tearoff=0)
            viewm.add_command(label="Toggle dark mode", command=self.toggle_theme)
            bar.add_cascade(label="View", menu=viewm)

            helpm = tk.Menu(bar, tearoff=0)
            helpm.add_command(label="About", command=self._about)
            helpm.add_command(label="Open project page (quickopen.ai)",
                              command=lambda: open_with_default_app(PROJECT_URL))
            bar.add_cascade(label="Help", menu=helpm)
            self.configure(menu=bar)
            self.bind_all("<Control-o>", lambda e: self._open_file())

        def _fill_recent_menu(self):
            self._recent_menu.delete(0, "end")
            recent = guiconfig.get_recent()
            if not recent:
                self._recent_menu.add_command(label="(none)", state="disabled")
                return
            for path in recent:
                exists = os.path.exists(path)
                label = path if exists else path + "   (missing)"
                self._recent_menu.add_command(
                    label=label, state="normal" if exists else "disabled",
                    command=(lambda pp=path: open_with_default_app(pp)))
            self._recent_menu.add_separator()
            self._recent_menu.add_command(label="Clear list",
                                          command=self._clear_recent)

        def _clear_recent(self):
            guiconfig.clear_recent()
            self._fill_recent_menu()

        def _open_file(self):
            p = filedialog.askopenfilename(title="Open a PDF", filetypes=PDF_TYPES)
            if p:
                self.remember_input(p)
                # route to the Info panel so "Open" does something useful
                self._select_tool("info")
                panel = self._panels.get("info")
                if panel and hasattr(panel, "load_path"):
                    panel.load_path(p)

        # ---- layout
        def _build_layout(self):
            # top brand bar
            top = ttk.Frame(self, style="Sidebar.TFrame", padding=(12, 8))
            top.pack(fill="x", side="top")
            ttk.Label(top, text="PDF Toolkit", style="Brand.TLabel").pack(side="left")
            ttk.Label(top, style="Status.TLabel",
                      text="  offline · open source · by QuickOpen").pack(side="left")
            self._theme_btn = ttk.Button(
                top, style="Toggle.TButton", command=self.toggle_theme,
                text="☀ Light mode" if self.theme == "dark" else "🌙 Dark mode")
            self._theme_btn.pack(side="right")

            body = ttk.Frame(self, style="TFrame")
            body.pack(fill="both", expand=True)

            # sidebar
            side = ttk.Frame(body, style="Sidebar.TFrame", width=220)
            side.pack(side="left", fill="y")
            side.pack_propagate(False)
            self.nav = ttk.Treeview(side, show="tree", selectmode="browse",
                                    style="Sidebar.Treeview")
            self.nav.pack(fill="both", expand=True, padx=6, pady=6)
            self._nav_ids = {}
            for cat, tools in TOOL_TREE:
                cid = self.nav.insert("", "end", text=cat, open=True,
                                      tags=("cat",))
                for tid, label in tools:
                    iid = self.nav.insert(cid, "end", text="   " + label)
                    self._nav_ids[iid] = tid
            self.nav.tag_configure("cat", font=(FONT, 10, "bold"))
            self.nav.bind("<<TreeviewSelect>>", self._on_nav_select)

            # main area: header + swappable body + result bar
            main = ttk.Frame(body, style="TFrame", padding=(16, 12))
            main.pack(side="left", fill="both", expand=True)

            head = ttk.Frame(main, style="TFrame")
            head.pack(fill="x")
            self.title_lbl = ttk.Label(head, text="Welcome", style="Header.TLabel")
            self.title_lbl.pack(anchor="w")
            self.desc_lbl = ttk.Label(head, text="", style="Sub.TLabel",
                                      wraplength=700, justify="left")
            self.desc_lbl.pack(anchor="w", pady=(2, 8))
            ttk.Separator(main).pack(fill="x")

            self.container = ttk.Frame(main, style="TFrame")
            self.container.pack(fill="both", expand=True, pady=(10, 8))

            # result / status bar (shared, inline)
            bar = ttk.Frame(self, style="Sidebar.TFrame", padding=(12, 6))
            bar.pack(fill="x", side="bottom")
            self.status_lbl = ttk.Label(bar, text="Ready", style="Status.TLabel",
                                        width=16, anchor="w")
            self.status_lbl.pack(side="left")
            self.openfolder_btn = ttk.Button(bar, text="Open folder",
                                             command=self._open_last_folder)
            self.result_lbl = ttk.Label(bar, text="", style="Status.TLabel",
                                        anchor="w", wraplength=680, justify="left")
            self.result_lbl.pack(side="left", fill="x", expand=True, padx=8)

        def _select_first_tool(self):
            for iid, tid in self._nav_ids.items():
                self.nav.selection_set(iid)
                self.nav.see(iid)
                break

        def _select_tool(self, tool_id):
            for iid, tid in self._nav_ids.items():
                if tid == tool_id:
                    self.nav.selection_set(iid)
                    self.nav.see(iid)
                    return

        def _on_nav_select(self, _e=None):
            sel = self.nav.selection()
            if not sel:
                return
            tid = self._nav_ids.get(sel[0])
            if not tid:
                return  # a category row
            self._show_tool(tid)

        def _show_tool(self, tool_id):
            if self._current is not None:
                self._current.pack_forget()
            panel = self._panels.get(tool_id)
            if panel is None:
                panel = ttk.Frame(self.container, style="TFrame")
                builder = getattr(self, "_panel_" + tool_id, None)
                if builder:
                    builder(panel)
                else:
                    ttk.Label(panel, text="Not implemented.").pack()
                self._panels[tool_id] = panel
                self._apply_theme()  # theme any new tk widgets
            panel.pack(fill="both", expand=True)
            self._current = panel
            title, desc = self._tool_meta(tool_id)
            self.title_lbl.configure(text=title)
            self.desc_lbl.configure(text=desc)
            self._clear_result()

        def _tool_meta(self, tool_id):
            for _cat, tools in TOOL_TREE:
                for tid, label in tools:
                    if tid == tool_id:
                        return label, TOOL_DESCRIPTIONS.get(tid, "")
            return tool_id, ""

        # ---- background operation runner
        def _bg(self, work, on_ok, button=None, busy="Working…"):
            """Run ``work()`` off the UI thread; call ``on_ok(result)`` back on it.

            Errors are shown inline (PdfToolkitError message, or a generic note),
            never as a traceback.  ``button`` (a ttk widget) is disabled while
            running.  Refuses to start a second op while one is in flight.
            """
            if self._busy:
                self._set_status("busy")
                self._show_error("Please wait — an operation is already running.")
                return
            self._busy = True
            if button is not None:
                try:
                    button.state(["disabled"])
                except Exception:
                    pass
            self._set_status(busy, kind="working")
            self._clear_result(keep_status=True)

            def run():
                try:
                    res, err = work(), None
                except PdfToolkitError as ex:
                    res, err = None, str(ex)
                except Exception as ex:  # never leak a traceback to the user
                    res, err = None, f"Unexpected error: {ex}"
                self.after(0, lambda: finish(res, err))

            def finish(res, err):
                self._busy = False
                if button is not None:
                    try:
                        button.state(["!disabled"])
                    except Exception:
                        pass
                if err is not None:
                    self._set_status("error", kind="err")
                    self._show_error(err)
                    return
                self._set_status("done", kind="ok")
                try:
                    on_ok(res)
                except Exception as ex:
                    self._show_error(f"Post-processing error: {ex}")

            threading.Thread(target=run, daemon=True).start()

        # ---- result bar helpers
        def _set_status(self, text, kind="idle"):
            p = self._pal()
            color = {"working": p["primary"], "ok": p["ok"], "err": p["err"]}.get(
                kind, p["muted"])
            self.status_lbl.configure(text=text, foreground=color)

        def _clear_result(self, keep_status=False):
            self.result_lbl.configure(text="")
            self.openfolder_btn.pack_forget()
            if not keep_status:
                self._set_status("Ready")

        def _show_error(self, message):
            self.result_lbl.configure(text="✕ " + message,
                                      foreground=self._pal()["err"])
            self.openfolder_btn.pack_forget()

        def report_success(self, message, outputs=None):
            """Show a success line, record outputs and offer 'Open folder'."""
            outputs = outputs or []
            for o in outputs:
                if o:
                    self._history.append(o)
                    guiconfig.add_recent(o)
            self._fill_recent_menu()
            if outputs:
                self._last_output_dir = (
                    outputs[0] if os.path.isdir(outputs[0])
                    else os.path.dirname(os.path.abspath(outputs[0])))
                self.openfolder_btn.pack(side="right")
            self.result_lbl.configure(text="✓ " + message,
                                      foreground=self._pal()["ok"])
            self._set_status("done", kind="ok")

        def _open_last_folder(self):
            if self._last_output_dir:
                open_in_file_manager(self._last_output_dir)

        def remember_input(self, path):
            if path:
                guiconfig.add_recent(path)
                self._fill_recent_menu()

        def _show_history(self):
            win = tk.Toplevel(self)
            win.title("Session output history")
            win.geometry("640x360")
            win.configure(bg=self._pal()["bg"])
            ttk.Label(win, style="Sub.TLabel", padding=10,
                      text="Outputs produced in this session "
                           "(most ops write a NEW file, so there is no in-place "
                           "undo — revisit any output here).").pack(anchor="w")
            frame = ttk.Frame(win, style="TFrame")
            frame.pack(fill="both", expand=True, padx=10)
            lb = tk.Listbox(frame, activestyle="none")
            sb = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            lb.pack(side="left", fill="both", expand=True)
            self.track(lb, "listbox")
            for o in self._history:
                lb.insert("end", o)
            if not self._history:
                lb.insert("end", "(nothing produced yet)")

            def _open_sel(reveal=False):
                sel = lb.curselection()
                if not sel:
                    return
                path = lb.get(sel[0])
                if os.path.exists(path):
                    (open_in_file_manager if reveal else open_with_default_app)(path)

            btns = ttk.Frame(win, style="TFrame", padding=10)
            btns.pack(fill="x")
            ttk.Button(btns, text="Open", command=lambda: _open_sel(False)).pack(side="left")
            ttk.Button(btns, text="Open folder",
                       command=lambda: _open_sel(True)).pack(side="left", padx=6)
            ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")
            self._apply_theme()

        # ---- About
        def _about(self):
            win = tk.Toplevel(self)
            win.title("About PDF Toolkit")
            win.configure(bg=self._pal()["bg"])
            win.resizable(False, False)
            frm = ttk.Frame(win, style="TFrame", padding=18)
            frm.pack(fill="both", expand=True)
            ttk.Label(frm, text="PDF Toolkit", style="Header.TLabel").pack(anchor="w")
            ttk.Label(frm, text=f"Version {APP_VERSION}",
                      style="Sub.TLabel").pack(anchor="w", pady=(0, 8))
            ttk.Label(frm, style="TLabel", justify="left", wraplength=380,
                      text="A fast, fully-offline PDF toolkit — merge, split, "
                           "compress, convert, protect, watermark and more.\n\n"
                           "100% AI-built, open source, published on QuickOpen.\n"
                           "Nothing is ever uploaded anywhere.").pack(anchor="w")
            ttk.Label(frm, style="Sub.TLabel", justify="left", wraplength=380,
                      text="Licensed under Apache-2.0. Built on permissive "
                           "libraries: pypdf, pikepdf/qpdf, pypdfium2, Pillow, "
                           "reportlab.").pack(anchor="w", pady=(8, 4))
            link = ttk.Label(frm, text="Project page: quickopen.ai",
                             style="Ok.TLabel", cursor="hand2")
            link.pack(anchor="w", pady=(4, 10))
            link.bind("<Button-1>", lambda e: open_with_default_app(PROJECT_URL))
            ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e")
            win.transient(self)
            win.grab_set()

        # ---- thumbnails
        def make_thumbnail(self, pdf_path, page=1, target_w=520):
            """Render one page to a temp PNG and return (PhotoImage, scale_pxpt).

            ``scale_pxpt`` = rendered pixels per PDF point, so a canvas drawn at
            1:1 can map coordinates back to points.  Returns (None, None) on
            failure.  Keeps a reference so Tk doesn't GC the image.
            """
            try:
                meta = info(pdf_path)
                sizes = meta.get("page_sizes") or []
                if page < 1 or page > len(sizes):
                    page = 1
                w_pt = sizes[page - 1][0] if sizes else 612.0
                dpi = max(36, min(220, int(72.0 * target_w / max(1.0, w_pt))))
                out = pdf_to_images(pdf_path, self._tmpdir, fmt="png", dpi=dpi,
                                    pages_spec=str(page))
                if not out:
                    return None, None
                img = tk.PhotoImage(file=out[0])
                self._img_refs.append(img)
                return img, dpi / 72.0
            except Exception:
                return None, None

        # =====================================================================
        # PANELS  -- each wires widgets to exactly one (or a few) core calls.
        # =====================================================================

        def _spec_or_none(self, s):
            s = (s or "").strip()
            return s or None

        def _suggest_out(self, in_path, suffix, ext=".pdf"):
            if not in_path:
                return ""
            base, _ = os.path.splitext(in_path)
            return f"{base}{suffix}{ext}"

        # ---------- Organize ----------
        def _panel_merge(self, parent):
            ttk.Label(parent, text="Add PDFs, order them, then Merge:",
                      style="TLabel").pack(anchor="w")
            flist = FileList(parent, self)
            flist.pack(fill="both", expand=True, pady=6)
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Merge → PDF", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inputs = flist.items()
                dest = out.get()
                if len(inputs) < 2:
                    self._show_error("Add at least two PDFs to merge.")
                    return
                if not dest:
                    self._show_error("Choose an output file.")
                    return
                self._bg(lambda: merge(inputs, dest),
                         lambda n: self.report_success(
                             f"Merged {len(inputs)} files ({n} pages) → {dest}",
                             [dest]), button=run)

            run.configure(command=go)

        def _panel_split(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: self.remember_input(v))
            src.pack(fill="x", pady=4)
            outdir = FileRow(parent, self, "Output folder", mode="dir")
            outdir.pack(fill="x", pady=4)

            mode = tk.StringVar(value="pages")
            box = ttk.Labelframe(parent, text="Mode", padding=8)
            box.pack(fill="x", pady=6)
            ttk.Radiobutton(box, text="One file per page", value="pages",
                            variable=mode).pack(anchor="w")
            r2 = ttk.Frame(box, style="TFrame")
            r2.pack(fill="x")
            ttk.Radiobutton(r2, text="By ranges (comma-separated, e.g. 1-3,4-6):",
                            value="ranges", variable=mode).pack(side="left")
            ranges_var = tk.StringVar()
            ttk.Entry(r2, textvariable=ranges_var, width=22).pack(side="left", padx=6)
            r3 = ttk.Frame(box, style="TFrame")
            r3.pack(fill="x")
            ttk.Radiobutton(r3, text="Every N pages:", value="every",
                            variable=mode).pack(side="left")
            n_var = tk.StringVar(value="2")
            ttk.Spinbox(r3, from_=1, to=9999, textvariable=n_var,
                        width=6).pack(side="left", padx=6)

            run = ttk.Button(parent, text="Split", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, d = src.get(), outdir.get()
                if not inp or not d:
                    self._show_error("Choose an input PDF and an output folder.")
                    return
                m = mode.get()
                if m == "ranges":
                    specs = [s.strip() for s in ranges_var.get().split(",") if s.strip()]
                    if not specs:
                        self._show_error("Enter at least one range.")
                        return
                    work = lambda: split_ranges(inp, specs, d)
                elif m == "every":
                    try:
                        n = int(n_var.get())
                    except ValueError:
                        self._show_error("N must be a whole number.")
                        return
                    work = lambda: split_every(inp, n, d)
                else:
                    work = lambda: split_pages(inp, d)
                self._bg(work, lambda paths: self.report_success(
                    f"Wrote {len(paths)} file(s) to {d}", [d]), button=run)

            run.configure(command=go)

        def _pages_op_panel(self, parent, verb, core_fn, needs_spec=True,
                            suffix="_out"):
            """Shared scaffold for extract/delete/duplicate (input + spec + out)."""
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, suffix))))
            src.pack(fill="x", pady=4)
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text="Pages", width=14, anchor="w").pack(side="left")
            spec = tk.StringVar()
            ttk.Entry(row, textvariable=spec).pack(side="left", fill="x", expand=True)
            ttk.Label(parent, style="Muted.TLabel",
                      text="Page spec like  1-3,5,8-10  (1-based, order preserved)."
                      ).pack(anchor="w")
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text=verb, style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, dest, sp = src.get(), out.get(), spec.get().strip()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                if needs_spec and not sp:
                    self._show_error("Enter a page spec.")
                    return
                self._bg(lambda: core_fn(inp, dest, sp),
                         lambda n: self.report_success(
                             f"{verb}: wrote {n} page(s) → {dest}", [dest]),
                         button=run)

            run.configure(command=go)

        def _panel_extract(self, parent):
            self._pages_op_panel(parent, "Extract pages", extract, suffix="_extract")

        def _panel_delete(self, parent):
            self._pages_op_panel(parent, "Delete pages", delete, suffix="_deleted")

        def _panel_duplicate(self, parent):
            self._pages_op_panel(parent, "Duplicate pages", duplicate,
                                 suffix="_dup")

        def _panel_rotate(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_rot"))))
            src.pack(fill="x", pady=4)
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text="Rotation", width=14, anchor="w").pack(side="left")
            deg = tk.IntVar(value=90)
            for d in (90, 180, 270):
                ttk.Radiobutton(row, text=f"{d}°", value=d, variable=deg).pack(
                    side="left", padx=4)
            row2 = ttk.Frame(parent, style="TFrame")
            row2.pack(fill="x", pady=4)
            ttk.Label(row2, text="Pages", width=14, anchor="w").pack(side="left")
            spec = tk.StringVar()
            ttk.Entry(row2, textvariable=spec).pack(side="left", fill="x", expand=True)
            ttk.Label(parent, style="Muted.TLabel",
                      text="Leave pages blank for all pages.").pack(anchor="w")
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Rotate", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, dest = src.get(), out.get()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                sp = self._spec_or_none(spec.get())
                self._bg(lambda: rotate(inp, dest, deg.get(), sp),
                         lambda n: self.report_success(
                             f"Rotated {n} page(s) by {deg.get()}° → {dest}",
                             [dest]), button=run)

            run.configure(command=go)

        def _panel_reorder(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_reordered"))))
            src.pack(fill="x", pady=4)
            ttk.Button(parent, text="Load pages", command=lambda: load()).pack(
                anchor="w", pady=4)
            body = ttk.Frame(parent, style="TFrame")
            body.pack(fill="both", expand=True, pady=4)
            lb = tk.Listbox(body, height=10, activestyle="none",
                            selectmode="browse", exportselection=False)
            sb = ttk.Scrollbar(body, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            lb.pack(side="left", fill="both", expand=True)
            self.track(lb, "listbox")
            ctrl = ttk.Frame(parent, style="TFrame")
            ctrl.pack(fill="x")
            ttk.Button(ctrl, text="Up", width=4,
                       command=lambda: move(-1)).pack(side="left")
            ttk.Button(ctrl, text="Down", width=5,
                       command=lambda: move(1)).pack(side="left", padx=4)
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Apply new order", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def load():
                inp = src.get()
                if not inp:
                    self._show_error("Choose an input PDF first.")
                    return
                def ok(meta):
                    lb.delete(0, "end")
                    n = meta.get("page_count") or 0
                    if not n:
                        self._show_error("Could not read page count "
                                         "(encrypted?).")
                        return
                    for i in range(1, n + 1):
                        lb.insert("end", f"Page {i}")
                    self.report_success(f"Loaded {n} pages — reorder then apply.")
                self._bg(lambda: info(inp), ok)

            def move(delta):
                sel = lb.curselection()
                if not sel:
                    return
                i = sel[0]
                j = i + delta
                if j < 0 or j >= lb.size():
                    return
                text = lb.get(i)
                lb.delete(i)
                lb.insert(j, text)
                lb.selection_set(j)

            def go():
                inp, dest = src.get(), out.get()
                items = list(lb.get(0, "end"))
                if not inp or not dest:
                    self._show_error("Choose input, output, and load pages.")
                    return
                if not items:
                    self._show_error("Load the pages first.")
                    return
                order = [int(t.split()[1]) for t in items]
                self._bg(lambda: reorder(inp, dest, order),
                         lambda n: self.report_success(
                             f"Reordered {n} page(s) → {dest}", [dest]),
                         button=run)

            run.configure(command=go)

        # ---------- Convert ----------
        def _panel_images2pdf(self, parent):
            ttk.Label(parent, text="Add images in order, then convert:",
                      style="TLabel").pack(anchor="w")
            flist = FileList(parent, self, filetypes=IMAGE_TYPES)
            flist.pack(fill="both", expand=True, pady=6)
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text="Page size", width=14, anchor="w").pack(side="left")
            size = tk.StringVar(value="per image")
            ttk.Combobox(row, textvariable=size, state="readonly", width=14,
                         values=["per image", "A4", "letter", "legal"]).pack(side="left")
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Images → PDF", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                imgs = flist.items()
                dest = out.get()
                if not imgs:
                    self._show_error("Add at least one image.")
                    return
                if not dest:
                    self._show_error("Choose an output file.")
                    return
                ps = None if size.get() == "per image" else size.get()
                self._bg(lambda: images_to_pdf(imgs, dest, page_size=ps),
                         lambda n: self.report_success(
                             f"Wrote {n}-page PDF → {dest}", [dest]), button=run)

            run.configure(command=go)

        def _panel_pdf2images(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: self.remember_input(v))
            src.pack(fill="x", pady=4)
            outdir = FileRow(parent, self, "Output folder", mode="dir")
            outdir.pack(fill="x", pady=4)
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text="Format", width=14, anchor="w").pack(side="left")
            fmt = tk.StringVar(value="png")
            ttk.Combobox(row, textvariable=fmt, state="readonly", width=8,
                         values=["png", "jpg"]).pack(side="left")
            ttk.Label(row, text="DPI").pack(side="left", padx=(16, 4))
            dpi = tk.StringVar(value="150")
            ttk.Spinbox(row, from_=36, to=600, textvariable=dpi,
                        width=6).pack(side="left")
            run = ttk.Button(parent, text="PDF → Images", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, d = src.get(), outdir.get()
                if not inp or not d:
                    self._show_error("Choose an input PDF and an output folder.")
                    return
                try:
                    dv = int(dpi.get())
                except ValueError:
                    self._show_error("DPI must be a whole number.")
                    return
                self._bg(lambda: pdf_to_images(inp, d, fmt=fmt.get(), dpi=dv),
                         lambda paths: self.report_success(
                             f"Rendered {len(paths)} page(s) to {d}", [d]),
                         button=run)

            run.configure(command=go)

        def _panel_pdf2text(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: self.remember_input(v))
            src.pack(fill="x", pady=4)
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Button(row, text="Extract & show",
                       command=lambda: show()).pack(side="left")
            ttk.Button(row, text="Save as .txt…",
                       command=lambda: save()).pack(side="left", padx=6)
            body = ttk.Frame(parent, style="TFrame")
            body.pack(fill="both", expand=True, pady=6)
            txt = tk.Text(body, wrap="word", height=16)
            sb = ttk.Scrollbar(body, orient="vertical", command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)
            self.track(txt, "text")

            def show():
                inp = src.get()
                if not inp:
                    self._show_error("Choose an input PDF.")
                    return
                def ok(text):
                    txt.delete("1.0", "end")
                    txt.insert("1.0", text or "(no extractable text)")
                    self.report_success(f"Extracted {len(text)} characters.")
                self._bg(lambda: pdf_to_text(inp), ok)

            def save():
                inp = src.get()
                if not inp:
                    self._show_error("Choose an input PDF.")
                    return
                dest = filedialog.asksaveasfilename(
                    title="Save text", defaultextension=".txt",
                    filetypes=[("Text", "*.txt"), ("All files", "*.*")])
                if not dest:
                    return
                self._bg(lambda: pdf_to_text(inp, dest),
                         lambda text: self.report_success(
                             f"Saved {len(text)} chars → {dest}", [dest]))

        def _panel_extractimages(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: self.remember_input(v))
            src.pack(fill="x", pady=4)
            outdir = FileRow(parent, self, "Output folder", mode="dir")
            outdir.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Extract images", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, d = src.get(), outdir.get()
                if not inp or not d:
                    self._show_error("Choose an input PDF and an output folder.")
                    return
                self._bg(lambda: extract_images(inp, d),
                         lambda paths: self.report_success(
                             f"Extracted {len(paths)} image(s) to {d}", [d]),
                         button=run)

            run.configure(command=go)

        # ---------- Optimize ----------
        def _panel_compress(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_compressed"))))
            src.pack(fill="x", pady=4)
            box = ttk.Labelframe(parent, text="Level", padding=8)
            box.pack(fill="x", pady=6)
            level = tk.StringVar(value="medium")
            for lv, txt in (("low", "Low (best quality)"),
                            ("medium", "Medium"),
                            ("high", "High (smallest)")):
                ttk.Radiobutton(box, text=txt, value=lv, variable=level).pack(
                    side="left", padx=6)
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Compress", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, dest = src.get(), out.get()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                def ok(res):
                    o = human_size(res["original_size"])
                    n = human_size(res["new_size"])
                    pct = res["ratio"] * 100.0
                    self.report_success(
                        f"{o} → {n}  ({pct:.1f}% smaller, level {res['level']}) "
                        f"→ {dest}", [dest])
                self._bg(lambda: compress(inp, dest, level=level.get()), ok,
                         button=run)

            run.configure(command=go)

        def _simple_out_panel(self, parent, verb, core_fn, suffix):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, suffix))))
            src.pack(fill="x", pady=4)
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text=verb, style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, dest = src.get(), out.get()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                self._bg(lambda: core_fn(inp, dest),
                         lambda r: self.report_success(f"{verb} → {dest}", [dest]),
                         button=run)

            run.configure(command=go)

        def _panel_weboptimize(self, parent):
            self._simple_out_panel(parent, "Web-optimize (linearize)",
                                   web_optimize, "_web")

        def _panel_removemeta(self, parent):
            self._simple_out_panel(parent, "Remove metadata",
                                   remove_metadata, "_nometa")

        def _panel_repair(self, parent):
            self._simple_out_panel(parent, "Repair", repair, "_repaired")

        # ---------- Security ----------
        def _panel_protect(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_protected"))))
            src.pack(fill="x", pady=4)
            grid = ttk.Frame(parent, style="TFrame")
            grid.pack(fill="x", pady=4)
            ttk.Label(grid, text="User password", width=16, anchor="w").grid(
                row=0, column=0, sticky="w")
            user = tk.StringVar()
            ttk.Entry(grid, textvariable=user, show="•", width=28).grid(
                row=0, column=1, sticky="w", pady=2)
            ttk.Label(grid, text="Owner password", width=16, anchor="w").grid(
                row=1, column=0, sticky="w")
            owner = tk.StringVar()
            ttk.Entry(grid, textvariable=owner, show="•", width=28).grid(
                row=1, column=1, sticky="w", pady=2)
            ttk.Label(parent, style="Muted.TLabel",
                      text="Owner password defaults to the user password if left "
                           "blank. Empty user password = opens freely but still "
                           "permission-restricted.").pack(anchor="w")
            perms = ttk.Labelframe(parent, text="Permissions", padding=8)
            perms.pack(fill="x", pady=6)
            allow = {k: tk.BooleanVar(value=True)
                     for k in ("print", "copy", "modify", "annotate")}
            for k in ("print", "copy", "modify", "annotate"):
                ttk.Checkbutton(perms, text="Allow " + k,
                                variable=allow[k]).pack(side="left", padx=6)
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Protect (AES-256)",
                             style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, dest = src.get(), out.get()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                self._bg(lambda: protect(
                    inp, dest, user_password=user.get(),
                    owner_password=owner.get() or None,
                    allow_print=allow["print"].get(),
                    allow_copy=allow["copy"].get(),
                    allow_modify=allow["modify"].get(),
                    allow_annotate=allow["annotate"].get()),
                    lambda r: self.report_success(f"Encrypted → {dest}", [dest]),
                    button=run)

            run.configure(command=go)

        def _panel_unprotect(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_unlocked"))))
            src.pack(fill="x", pady=4)
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text="Password", width=14, anchor="w").pack(side="left")
            pw = tk.StringVar()
            ttk.Entry(row, textvariable=pw, show="•", width=28).pack(side="left")
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Unprotect", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, dest = src.get(), out.get()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                self._bg(lambda: unprotect(inp, dest, pw.get()),
                         lambda r: self.report_success(
                             f"Decrypted → {dest}", [dest]), button=run)

            run.configure(command=go)

        def _panel_encstatus(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: self.remember_input(v))
            src.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Check encryption status",
                             style="Accent.TButton")
            run.pack(anchor="w", pady=6)
            result = tk.Text(parent, height=8, wrap="word")
            result.pack(fill="both", expand=True, pady=6)
            self.track(result, "text")

            def go():
                inp = src.get()
                if not inp:
                    self._show_error("Choose an input PDF.")
                    return
                def ok(data):
                    enc, meta = data
                    result.delete("1.0", "end")
                    lines = [f"Encrypted: {'YES' if enc else 'no'}"]
                    if meta.get("file_size") is not None:
                        lines.append(f"File size: {human_size(meta['file_size'])}")
                    pc = meta.get("page_count")
                    lines.append(f"Pages: {pc if pc is not None else '(hidden — encrypted)'}")
                    result.insert("1.0", "\n".join(lines))
                    self.report_success("Encrypted." if enc else "Not encrypted.")
                self._bg(lambda: (is_encrypted(inp), info(inp)), ok, button=run)

            run.configure(command=go)

        # ---------- Watermark ----------
        def _panel_textwm(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_wm"))))
            src.pack(fill="x", pady=4)
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text="Text", width=14, anchor="w").pack(side="left")
            text = tk.StringVar(value="CONFIDENTIAL")
            ttk.Entry(row, textvariable=text).pack(side="left", fill="x", expand=True)

            grid = ttk.Frame(parent, style="TFrame")
            grid.pack(fill="x", pady=4)
            ttk.Label(grid, text="Position").grid(row=0, column=0, sticky="w")
            pos = tk.StringVar(value="center")
            ttk.Combobox(grid, textvariable=pos, state="readonly", width=14,
                         values=WM_POSITIONS).grid(row=0, column=1, padx=6)
            ttk.Label(grid, text="Rotation°").grid(row=0, column=2, sticky="w")
            rot = tk.StringVar(value="45")
            ttk.Spinbox(grid, from_=-180, to=180, textvariable=rot,
                        width=6).grid(row=0, column=3, padx=6)
            ttk.Label(grid, text="Font size").grid(row=0, column=4, sticky="w")
            fsize = tk.StringVar(value="48")
            ttk.Spinbox(grid, from_=6, to=300, textvariable=fsize,
                        width=6).grid(row=0, column=5, padx=6)

            orow = ttk.Frame(parent, style="TFrame")
            orow.pack(fill="x", pady=4)
            ttk.Label(orow, text="Opacity", width=14, anchor="w").pack(side="left")
            opacity = tk.DoubleVar(value=0.3)
            ttk.Scale(orow, from_=0.05, to=1.0, variable=opacity,
                      orient="horizontal").pack(side="left", fill="x", expand=True)
            opval = ttk.Label(orow, text="0.30", style="Muted.TLabel", width=5)
            opval.pack(side="left")
            opacity.trace_add("write",
                              lambda *_: opval.configure(text=f"{opacity.get():.2f}"))

            prow = ttk.Frame(parent, style="TFrame")
            prow.pack(fill="x", pady=4)
            ttk.Label(prow, text="Pages", width=14, anchor="w").pack(side="left")
            spec = tk.StringVar()
            ttk.Entry(prow, textvariable=spec).pack(side="left", fill="x", expand=True)
            ttk.Label(parent, style="Muted.TLabel",
                      text="Leave pages blank for all pages.").pack(anchor="w")

            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            brow = ttk.Frame(parent, style="TFrame")
            brow.pack(anchor="w", pady=6)
            run = ttk.Button(brow, text="Apply watermark", style="Accent.TButton")
            run.pack(side="left")
            prev = ttk.Button(brow, text="Preview page 1")
            prev.pack(side="left", padx=6)
            thumb = ttk.Label(parent, style="TLabel")
            thumb.pack(anchor="w", pady=6)

            def params():
                return dict(text=text.get(), opacity=float(opacity.get()),
                            position=pos.get(), rotation=int(float(rot.get())),
                            font_size=int(float(fsize.get())))

            def go():
                inp, dest = src.get(), out.get()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                sp = self._spec_or_none(spec.get())
                self._bg(lambda: text_watermark(inp, dest, pages_spec=sp, **params()),
                         lambda n: self.report_success(
                             f"Watermarked {n} page(s) → {dest}", [dest]),
                         button=run)

            def preview():
                inp = src.get()
                if not inp:
                    self._show_error("Choose an input PDF for preview.")
                    return
                tmp = os.path.join(self._tmpdir, "wm_preview.pdf")
                def ok(_n):
                    img, _ = self.make_thumbnail(tmp, 1, target_w=420)
                    if img:
                        thumb.configure(image=img)
                        thumb.image = img
                    self.report_success("Preview rendered (page 1).")
                self._bg(lambda: text_watermark(inp, tmp, pages_spec="1", **params()),
                         ok, button=prev)

            run.configure(command=go)
            prev.configure(command=preview)

        def _panel_imagewm(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_wm"))))
            src.pack(fill="x", pady=4)
            img = FileRow(parent, self, "Watermark image", mode="open_any",
                          filetypes=IMAGE_TYPES)
            img.pack(fill="x", pady=4)
            grid = ttk.Frame(parent, style="TFrame")
            grid.pack(fill="x", pady=4)
            ttk.Label(grid, text="Position").grid(row=0, column=0, sticky="w")
            pos = tk.StringVar(value="center")
            ttk.Combobox(grid, textvariable=pos, state="readonly", width=14,
                         values=WM_POSITIONS).grid(row=0, column=1, padx=6)
            ttk.Label(grid, text="Scale").grid(row=0, column=2, sticky="w")
            scale = tk.DoubleVar(value=0.5)
            ttk.Spinbox(grid, from_=0.05, to=1.0, increment=0.05,
                        textvariable=scale, width=6).grid(row=0, column=3, padx=6)
            orow = ttk.Frame(parent, style="TFrame")
            orow.pack(fill="x", pady=4)
            ttk.Label(orow, text="Opacity", width=14, anchor="w").pack(side="left")
            opacity = tk.DoubleVar(value=0.3)
            ttk.Scale(orow, from_=0.05, to=1.0, variable=opacity,
                      orient="horizontal").pack(side="left", fill="x", expand=True)
            opval = ttk.Label(orow, text="0.30", style="Muted.TLabel", width=5)
            opval.pack(side="left")
            opacity.trace_add("write",
                              lambda *_: opval.configure(text=f"{opacity.get():.2f}"))
            prow = ttk.Frame(parent, style="TFrame")
            prow.pack(fill="x", pady=4)
            ttk.Label(prow, text="Pages", width=14, anchor="w").pack(side="left")
            spec = tk.StringVar()
            ttk.Entry(prow, textvariable=spec).pack(side="left", fill="x", expand=True)
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Apply image watermark",
                             style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, dest, ip = src.get(), out.get(), img.get()
                if not inp or not dest or not ip:
                    self._show_error("Choose input PDF, image, and output.")
                    return
                sp = self._spec_or_none(spec.get())
                self._bg(lambda: image_watermark(
                    inp, dest, ip, opacity=float(opacity.get()),
                    position=pos.get(), scale=float(scale.get()), pages_spec=sp),
                    lambda n: self.report_success(
                        f"Watermarked {n} page(s) → {dest}", [dest]), button=run)

            run.configure(command=go)

        # ---------- Pages/Meta ----------
        def _panel_pagenumbers(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_numbered"))))
            src.pack(fill="x", pady=4)
            grid = ttk.Frame(parent, style="TFrame")
            grid.pack(fill="x", pady=4)
            ttk.Label(grid, text="Position").grid(row=0, column=0, sticky="w")
            pos = tk.StringVar(value="bottom-center")
            ttk.Combobox(grid, textvariable=pos, state="readonly", width=14,
                         values=POSITIONS).grid(row=0, column=1, padx=6)
            ttk.Label(grid, text="Start at").grid(row=0, column=2, sticky="w")
            start = tk.StringVar(value="1")
            ttk.Spinbox(grid, from_=0, to=99999, textvariable=start,
                        width=6).grid(row=0, column=3, padx=6)
            ttk.Label(grid, text="Format").grid(row=0, column=4, sticky="w")
            fmt = tk.StringVar(value="{n}")
            ttk.Entry(grid, textvariable=fmt, width=12).grid(row=0, column=5, padx=6)
            ttk.Label(parent, style="Muted.TLabel",
                      text="Format supports {n} (this page) and {total}, "
                           "e.g. “Page {n} of {total}”.").pack(anchor="w")
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Add page numbers",
                             style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, dest = src.get(), out.get()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                try:
                    st = int(start.get())
                except ValueError:
                    self._show_error("Start must be a whole number.")
                    return
                self._bg(lambda: add_page_numbers(
                    inp, dest, position=pos.get(), start=st, fmt=fmt.get()),
                    lambda n: self.report_success(
                        f"Numbered {n} page(s) → {dest}", [dest]), button=run)

            run.configure(command=go)

        def _panel_headerfooter(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_hf"))))
            src.pack(fill="x", pady=4)
            r1 = ttk.Frame(parent, style="TFrame")
            r1.pack(fill="x", pady=4)
            ttk.Label(r1, text="Header", width=14, anchor="w").pack(side="left")
            header = tk.StringVar()
            ttk.Entry(r1, textvariable=header).pack(side="left", fill="x", expand=True)
            r2 = ttk.Frame(parent, style="TFrame")
            r2.pack(fill="x", pady=4)
            ttk.Label(r2, text="Footer", width=14, anchor="w").pack(side="left")
            footer = tk.StringVar()
            ttk.Entry(r2, textvariable=footer).pack(side="left", fill="x", expand=True)
            ttk.Label(parent, style="Muted.TLabel",
                      text="Both are centred; provide at least one.").pack(anchor="w")
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Add header/footer",
                             style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inp, dest = src.get(), out.get()
                h = header.get().strip() or None
                f = footer.get().strip() or None
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                if not h and not f:
                    self._show_error("Enter a header and/or a footer.")
                    return
                self._bg(lambda: add_header_footer(inp, dest, header=h, footer=f),
                         lambda n: self.report_success(
                             f"Stamped {n} page(s) → {dest}", [dest]), button=run)

            run.configure(command=go)

        def _panel_metadata(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_meta"))))
            src.pack(fill="x", pady=4)
            ttk.Button(parent, text="Load current metadata",
                       command=lambda: load()).pack(anchor="w", pady=4)
            grid = ttk.Frame(parent, style="TFrame")
            grid.pack(fill="x", pady=4)
            fields = {}
            for i, key in enumerate(("title", "author", "subject", "keywords")):
                ttk.Label(grid, text=key.title(), width=12, anchor="w").grid(
                    row=i, column=0, sticky="w", pady=2)
                var = tk.StringVar()
                ttk.Entry(grid, textvariable=var, width=48).grid(
                    row=i, column=1, sticky="we", pady=2)
                fields[key] = var
            grid.columnconfigure(1, weight=1)
            ro = tk.Text(parent, height=6, wrap="word")
            ro.pack(fill="x", pady=6)
            self.track(ro, "text")
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Save metadata", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def load():
                inp = src.get()
                if not inp:
                    self._show_error("Choose an input PDF first.")
                    return
                def ok(meta):
                    for k in ("title", "author", "subject", "keywords"):
                        fields[k].set(meta.get(k) or "")
                    ro.delete("1.0", "end")
                    extra = [f"{k}: {meta.get(k)}" for k in
                             ("creator", "producer", "creation_date", "mod_date")]
                    ro.insert("1.0", "Read-only fields —\n" + "\n".join(extra))
                    self.report_success("Loaded metadata.")
                self._bg(lambda: get_metadata(inp), ok)

            def go():
                inp, dest = src.get(), out.get()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                kw = {k: (fields[k].get().strip() or None)
                      for k in ("title", "author", "subject", "keywords")}
                self._bg(lambda: set_metadata(inp, dest, **kw),
                         lambda r: self.report_success(
                             f"Saved metadata → {dest}", [dest]), button=run)

            run.configure(command=go)

        def _panel_bookmarks(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_toc"))))
            src.pack(fill="x", pady=4)
            ttk.Button(parent, text="List bookmarks",
                       command=lambda: load()).pack(anchor="w", pady=4)
            tree = ttk.Treeview(parent, columns=("page",), show="tree headings",
                                height=8)
            tree.heading("#0", text="Bookmark")
            tree.heading("page", text="Page")
            tree.column("page", width=70, anchor="center")
            tree.pack(fill="both", expand=True, pady=4)

            addbox = ttk.Labelframe(parent, text="Build a new flat outline "
                                    "(title → page), then save", padding=8)
            addbox.pack(fill="x", pady=6)
            entries = []
            elist = tk.Listbox(addbox, height=4, activestyle="none")
            elist.pack(fill="x")
            self.track(elist, "listbox")
            frm = ttk.Frame(addbox, style="TFrame")
            frm.pack(fill="x", pady=4)
            t_var = tk.StringVar()
            p_var = tk.StringVar()
            ttk.Label(frm, text="Title").pack(side="left")
            ttk.Entry(frm, textvariable=t_var, width=24).pack(side="left", padx=4)
            ttk.Label(frm, text="Page").pack(side="left")
            ttk.Entry(frm, textvariable=p_var, width=6).pack(side="left", padx=4)

            def add_entry():
                t = t_var.get().strip()
                try:
                    p = int(p_var.get())
                except ValueError:
                    self._show_error("Page must be a whole number.")
                    return
                if not t:
                    self._show_error("Enter a bookmark title.")
                    return
                entries.append((t, p))
                elist.insert("end", f"{t}  →  p.{p}")
                t_var.set("")
                p_var.set("")

            ttk.Button(frm, text="Add entry", command=add_entry).pack(side="left", padx=4)
            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Write outline", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def load():
                inp = src.get()
                if not inp:
                    self._show_error("Choose an input PDF first.")
                    return
                def ok(items):
                    tree.delete(*tree.get_children())
                    stack = {0: ""}
                    for b in items:
                        lvl = b.get("level", 0)
                        parent_iid = stack.get(lvl, "")
                        iid = tree.insert(parent_iid, "end", text=b["title"],
                                          values=(b.get("page") or "",))
                        stack[lvl + 1] = iid
                    self.report_success(f"Found {len(items)} bookmark(s).")
                self._bg(lambda: list_bookmarks(inp), ok)

            def go():
                inp, dest = src.get(), out.get()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                if not entries:
                    self._show_error("Add at least one outline entry.")
                    return
                self._bg(lambda: generate_toc(inp, dest, list(entries)),
                         lambda n: self.report_success(
                             f"Wrote {n} bookmark(s) → {dest}", [dest]), button=run)

            run.configure(command=go)

        def _panel_info(self, parent):
            src = FileRow(parent, self, "Input PDF",
                          on_change=lambda v: self.remember_input(v))
            src.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Load info", style="Accent.TButton")
            run.pack(anchor="w", pady=6)
            body = ttk.Frame(parent, style="TFrame")
            body.pack(fill="both", expand=True, pady=6)
            txt = tk.Text(body, wrap="word", height=16)
            sb = ttk.Scrollbar(body, orient="vertical", command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)
            self.track(txt, "text")

            def load(meta):
                txt.delete("1.0", "end")
                lines = [
                    f"Path       : {meta.get('path')}",
                    f"File size  : {human_size(meta.get('file_size') or 0)}",
                    f"Encrypted  : {'YES' if meta.get('encrypted') else 'no'}",
                    f"Page count : {meta.get('page_count')}",
                ]
                sizes = meta.get("page_sizes") or []
                if sizes:
                    lines.append("")
                    lines.append("Page sizes (points):")
                    for i, (w, h) in enumerate(sizes[:50], 1):
                        lines.append(f"  page {i}: {w} × {h}")
                    if len(sizes) > 50:
                        lines.append(f"  … (+{len(sizes) - 50} more)")
                md = meta.get("metadata") or {}
                lines.append("")
                lines.append("Metadata:")
                for k, v in md.items():
                    lines.append(f"  {k}: {v}")
                txt.insert("1.0", "\n".join(lines))
                self.report_success("Loaded document info.")

            def go():
                inp = src.get()
                if not inp:
                    self._show_error("Choose an input PDF.")
                    return
                self._bg(lambda: info(inp), load, button=run)

            def load_path(p):
                src.set(p)
                go()

            parent.load_path = load_path  # File>Open routes here
            run.configure(command=go)

        # ---------- Advanced ----------
        def _panel_redact(self, parent):
            ttk.Label(parent, style="Muted.TLabel", wraplength=720, justify="left",
                      text="Draw black boxes on a rendered page, then apply. "
                           "KNOWN LIMITATION: this hides content visually and is "
                           "best-effort at removing the underlying text — it is "
                           "NOT guaranteed high-assurance redaction (see the core "
                           "docs). One page at a time.").pack(anchor="w", pady=(0, 6))
            top = ttk.Frame(parent, style="TFrame")
            top.pack(fill="x", pady=4)
            src = FileRow(top, self, "Input PDF",
                          on_change=lambda v: (self.remember_input(v),
                                               out.set(self._suggest_out(v, "_redacted"))))
            src.pack(fill="x")
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text="Page", width=14, anchor="w").pack(side="left")
            page = tk.StringVar(value="1")
            ttk.Spinbox(row, from_=1, to=99999, textvariable=page,
                        width=6).pack(side="left")
            ttk.Button(row, text="Render page",
                       command=lambda: render()).pack(side="left", padx=8)
            ttk.Button(row, text="Clear boxes",
                       command=lambda: clear()).pack(side="left")

            cv_wrap = ttk.Frame(parent, style="TFrame")
            cv_wrap.pack(fill="both", expand=True, pady=6)
            canvas = tk.Canvas(cv_wrap, width=420, height=520, highlightthickness=1)
            canvas.pack(anchor="w")
            self.track(canvas, "canvas")

            out = FileRow(parent, self, "Save as", mode="save_pdf")
            out.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Apply redaction",
                             style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            state = {"scale": None, "img_h": 0, "rects": [], "start": None,
                     "cur": None}

            def render():
                inp = src.get()
                if not inp:
                    self._show_error("Choose an input PDF.")
                    return
                try:
                    pg = int(page.get())
                except ValueError:
                    self._show_error("Page must be a whole number.")
                    return
                def ok(result):
                    img, scale = result
                    if not img:
                        self._show_error("Could not render this page.")
                        return
                    canvas.delete("all")
                    state["rects"].clear()
                    state["scale"] = scale
                    state["img_h"] = img.height()
                    canvas.configure(width=img.width(), height=img.height())
                    canvas.create_image(0, 0, anchor="nw", image=img)
                    canvas.image = img
                    self.report_success("Page rendered — drag to draw boxes.")
                self._bg(lambda: self.make_thumbnail(inp, pg, target_w=420), ok)

            def clear():
                for rid in [r["id"] for r in state["rects"]]:
                    canvas.delete(rid)
                state["rects"].clear()

            def on_down(e):
                state["start"] = (canvas.canvasx(e.x), canvas.canvasy(e.y))
                state["cur"] = canvas.create_rectangle(
                    e.x, e.y, e.x, e.y, outline="#ff3b30", width=2,
                    fill="#000000", stipple="gray50")

            def on_drag(e):
                if state["cur"] is not None and state["start"] is not None:
                    x0, y0 = state["start"]
                    canvas.coords(state["cur"], x0, y0,
                                  canvas.canvasx(e.x), canvas.canvasy(e.y))

            def on_up(e):
                if state["cur"] is None or state["start"] is None:
                    return
                x0, y0 = state["start"]
                x1, y1 = canvas.canvasx(e.x), canvas.canvasy(e.y)
                if abs(x1 - x0) > 3 and abs(y1 - y0) > 3:
                    state["rects"].append(
                        {"id": state["cur"], "px": (x0, y0, x1, y1)})
                else:
                    canvas.delete(state["cur"])
                state["cur"] = None
                state["start"] = None

            canvas.bind("<ButtonPress-1>", on_down)
            canvas.bind("<B1-Motion>", on_drag)
            canvas.bind("<ButtonRelease-1>", on_up)

            def go():
                inp, dest = src.get(), out.get()
                if not inp or not dest:
                    self._show_error("Choose an input and an output file.")
                    return
                if state["scale"] is None:
                    self._show_error("Render the page first.")
                    return
                if not state["rects"]:
                    self._show_error("Draw at least one box.")
                    return
                scale = state["scale"]
                img_h = state["img_h"]
                rects_pt = []
                for r in state["rects"]:
                    x0, y0, x1, y1 = r["px"]
                    # canvas px -> PDF points, flip Y (origin bottom-left)
                    rects_pt.append((
                        x0 / scale, (img_h - y0) / scale,
                        x1 / scale, (img_h - y1) / scale))
                try:
                    pg = int(page.get())
                except ValueError:
                    self._show_error("Page must be a whole number.")
                    return
                self._bg(lambda: redact_rects(inp, dest, pg, rects_pt),
                         lambda n: self.report_success(
                             f"Redacted {n} box(es) on page {pg} → {dest}",
                             [dest]), button=run)

            run.configure(command=go)

        def _panel_compare(self, parent):
            a = FileRow(parent, self, "PDF A",
                        on_change=lambda v: self.remember_input(v))
            a.pack(fill="x", pady=4)
            b = FileRow(parent, self, "PDF B",
                        on_change=lambda v: self.remember_input(v))
            b.pack(fill="x", pady=4)
            run = ttk.Button(parent, text="Compare", style="Accent.TButton")
            run.pack(anchor="w", pady=6)
            body = ttk.Frame(parent, style="TFrame")
            body.pack(fill="both", expand=True, pady=6)
            txt = tk.Text(body, wrap="word", height=16)
            sb = ttk.Scrollbar(body, orient="vertical", command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)
            self.track(txt, "text")

            def go():
                pa, pb = a.get(), b.get()
                if not pa or not pb:
                    self._show_error("Choose two PDFs to compare.")
                    return
                def ok(res):
                    txt.delete("1.0", "end")
                    head = ("IDENTICAL text." if res["identical"] else
                            f"DIFFERENT — +{res['total_added']} / "
                            f"-{res['total_removed']} lines across pages.")
                    lines = [head, ""]
                    for pg in res["pages"]:
                        if pg["changed"]:
                            lines.append(
                                f"  page {pg['page']}: +{pg['added']} / "
                                f"-{pg['removed']}")
                    if len(lines) == 2:
                        lines.append("  (no per-page changes)")
                    txt.insert("1.0", "\n".join(lines))
                    self.report_success(head)
                self._bg(lambda: compare_text(pa, pb), ok, button=run)

            run.configure(command=go)

        # ---------- Batch ----------
        def _batch_scaffold(self, parent):
            ttk.Label(parent, text="Pick multiple PDFs and an output folder:",
                      style="TLabel").pack(anchor="w")
            flist = FileList(parent, self)
            flist.pack(fill="both", expand=True, pady=6)
            outdir = FileRow(parent, self, "Output folder", mode="dir")
            outdir.pack(fill="x", pady=4)
            return flist, outdir

        def _panel_batchcompress(self, parent):
            flist, outdir = self._batch_scaffold(parent)
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text="Level", width=14, anchor="w").pack(side="left")
            level = tk.StringVar(value="medium")
            for lv in ("low", "medium", "high"):
                ttk.Radiobutton(row, text=lv, value=lv, variable=level).pack(
                    side="left", padx=6)
            run = ttk.Button(parent, text="Batch compress", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inputs, d = flist.items(), outdir.get()
                if not inputs or not d:
                    self._show_error("Add PDFs and choose an output folder.")
                    return
                self._bg(lambda: batch_compress(inputs, d, level=level.get()),
                         lambda res: self.report_success(
                             f"Compressed {len(res)} file(s) → {d}", [d]),
                         button=run)

            run.configure(command=go)

        def _panel_batchwatermark(self, parent):
            flist, outdir = self._batch_scaffold(parent)
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text="Text", width=14, anchor="w").pack(side="left")
            text = tk.StringVar(value="CONFIDENTIAL")
            ttk.Entry(row, textvariable=text).pack(side="left", fill="x", expand=True)
            row2 = ttk.Frame(parent, style="TFrame")
            row2.pack(fill="x", pady=4)
            ttk.Label(row2, text="Position", width=14, anchor="w").pack(side="left")
            pos = tk.StringVar(value="center")
            ttk.Combobox(row2, textvariable=pos, state="readonly", width=14,
                         values=WM_POSITIONS).pack(side="left")
            run = ttk.Button(parent, text="Batch watermark", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inputs, d = flist.items(), outdir.get()
                if not inputs or not d:
                    self._show_error("Add PDFs and choose an output folder.")
                    return
                if not text.get().strip():
                    self._show_error("Enter watermark text.")
                    return
                self._bg(lambda: batch_watermark(
                    inputs, d, text.get(), position=pos.get()),
                    lambda res: self.report_success(
                        f"Watermarked {len(res)} file(s) → {d}", [d]), button=run)

            run.configure(command=go)

        def _panel_batchimages(self, parent):
            flist, outdir = self._batch_scaffold(parent)
            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text="Format", width=14, anchor="w").pack(side="left")
            fmt = tk.StringVar(value="png")
            ttk.Combobox(row, textvariable=fmt, state="readonly", width=8,
                         values=["png", "jpg"]).pack(side="left")
            ttk.Label(row, text="DPI").pack(side="left", padx=(16, 4))
            dpi = tk.StringVar(value="150")
            ttk.Spinbox(row, from_=36, to=600, textvariable=dpi,
                        width=6).pack(side="left")
            run = ttk.Button(parent, text="Batch → images", style="Accent.TButton")
            run.pack(anchor="w", pady=6)

            def go():
                inputs, d = flist.items(), outdir.get()
                if not inputs or not d:
                    self._show_error("Add PDFs and choose an output folder.")
                    return
                try:
                    dv = int(dpi.get())
                except ValueError:
                    self._show_error("DPI must be a whole number.")
                    return
                self._bg(lambda: batch_convert_to_images(
                    inputs, d, fmt=fmt.get(), dpi=dv),
                    lambda res: self.report_success(
                        f"Rendered {len(res)} file(s) into subfolders of {d}",
                        [d]), button=run)

            run.configure(command=go)

        # ---- shutdown
        def _on_close(self):
            try:
                import shutil
                shutil.rmtree(self._tmpdir, ignore_errors=True)
            except Exception:
                pass
            self.destroy()

    return App


TOOL_DESCRIPTIONS = {
    "merge": "Concatenate several PDFs into one. Reorder before merging.",
    "split": "Split into single pages, by page ranges, or every N pages.",
    "extract": "Keep only the pages you list (order preserved).",
    "delete": "Remove the pages you list.",
    "rotate": "Rotate pages by 90/180/270°, all pages or a range.",
    "reorder": "Rearrange pages into a new order.",
    "duplicate": "Emit selected pages twice, in place.",
    "images2pdf": "Combine images into a single PDF (order preserved).",
    "pdf2images": "Render pages to PNG/JPG at a chosen DPI.",
    "pdf2text": "Extract text — view it or save a .txt.",
    "extractimages": "Save the raster images embedded in a PDF.",
    "compress": "Shrink a PDF (low/medium/high). Never larger than the input.",
    "weboptimize": "Linearize for fast web view.",
    "removemeta": "Strip the /Info dictionary and XMP metadata.",
    "protect": "Encrypt with AES-256 and set permissions.",
    "unprotect": "Decrypt with the password.",
    "encstatus": "Check whether a PDF is encrypted.",
    "textwm": "Stamp a text watermark; opacity, position, rotation, size.",
    "imagewm": "Stamp an image watermark; opacity, position, scale.",
    "pagenumbers": "Add page numbers with a position, start value and format.",
    "headerfooter": "Add a centred header and/or footer to every page.",
    "metadata": "View and edit title/author/subject/keywords.",
    "bookmarks": "List existing bookmarks or build a new flat outline.",
    "info": "Page count, size, encryption state and page sizes.",
    "redact": "Draw black boxes on a page and flatten them in.",
    "compare": "Per-page text diff summary between two PDFs.",
    "repair": "Rebuild a damaged PDF via qpdf recovery.",
    "batchcompress": "Compress many PDFs into an output folder.",
    "batchwatermark": "Text-watermark many PDFs into an output folder.",
    "batchimages": "Render many PDFs to images (one subfolder each).",
}


def main():
    """Entry point: build the root window and run.  Degrades on headless hosts.

    Importing this module does nothing; only this function creates a Tk root.
    With no display (e.g. a server), it prints a friendly note and returns 0
    instead of raising.
    """
    try:
        import tkinter as tk
    except Exception as exc:  # tkinter missing entirely
        print(f"{APP_NAME}: a graphical environment with tkinter is required "
              f"to run the GUI ({exc}).")
        return 0

    try:
        App = build_app()
        app = App()
    except tk.TclError as exc:
        # Typically "no display name and no $DISPLAY environment variable".
        print(f"{APP_NAME}: no graphical display available — cannot start the "
              f"GUI here ({exc}). This app is intended for the Windows desktop.")
        return 0
    except Exception as exc:
        print(f"{APP_NAME}: could not start the GUI ({exc}).")
        return 1

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
