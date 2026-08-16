"""GUI tests for the 1.1.0 Aura layout-language rework (PDFgear-style Home).

Pure checks run anywhere; the App tests need a display (run the suite under
``xvfb-run -a python3 -m pytest``) and are skipped headless, mirroring the
house pattern.  Everything is hermetic via PDFTOOLKIT_HOME.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdftoolkit import gui, guiconfig  # noqa: E402


# ---------------------------------------------------------------------------
# structure (no display needed)
# ---------------------------------------------------------------------------
def test_nav_curated_to_seven_pills():
    # Home + 5 curated categories + About (APP-LAYOUT-LANGUAGE.md: <= 7)
    assert len(gui.SECTIONS) == 7
    assert gui.SECTIONS[0] == ("home", "Home")
    assert gui.SECTIONS[-1] == ("about", "About")


def test_every_tool_is_reachable_and_described():
    nav_cats = [c for _sid, _l, _g, cats in gui.NAV_TREE for c in cats]
    for cat, tools in gui.TOOL_TREE:
        assert cat in nav_cats
        for tid, _label in tools:
            assert tid in gui.TOOL_DESCRIPTIONS
    for tid in gui.POPULAR_TOOLS:
        assert tid in gui.TOOL_DESCRIPTIONS


def test_theme_defaults_to_system(tmp_path, monkeypatch):
    monkeypatch.setenv("PDFTOOLKIT_HOME", str(tmp_path))
    assert guiconfig.get_theme() == "system"
    guiconfig.set_theme("dark")
    assert guiconfig.get_theme() == "dark"
    guiconfig.set_theme("bogus")
    assert guiconfig.get_theme() == "dark"
    guiconfig.set_theme("system")
    assert guiconfig.get_theme() == "system"


# ---------------------------------------------------------------------------
# the real window (Xvfb)
# ---------------------------------------------------------------------------
needs_display = pytest.mark.skipif(
    sys.platform == "win32" or not os.environ.get("DISPLAY"),
    reason="needs a display (run under xvfb-run)")


def _pump(a, seconds=0.5):
    end = time.time() + seconds
    while time.time() < end:
        a.update()
        time.sleep(0.02)


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    home = tmp_path_factory.mktemp("pt-home")
    old = os.environ.get("PDFTOOLKIT_HOME")
    os.environ["PDFTOOLKIT_HOME"] = str(home)
    App = gui.build_app()
    a = App()
    _pump(a, 0.8)
    yield a
    try:
        a.destroy()
    except Exception:
        pass
    if old is None:
        os.environ.pop("PDFTOOLKIT_HOME", None)
    else:
        os.environ["PDFTOOLKIT_HOME"] = old


@needs_display
def test_home_grid_and_search(app):
    assert app.active_section == "home"
    # all 29 tools present in the grid
    assert len(app._grid_frame.winfo_children()) == \
        sum(len(t) for _c, t in gui.TOOL_TREE)
    app.home_search.set("watermark")
    app._fill_tool_grid()
    n = len(app._grid_frame.winfo_children())
    assert 1 <= n < 10
    app.home_search.set("")
    app._fill_tool_grid()


@needs_display
def test_goto_tool_switches_section(app):
    app._goto_tool("compress")
    assert app.active_section == "optimize"
    app._goto_tool("textwm")
    assert app.active_section == "marks"
    app._goto_tool("batchcompress")
    assert app.active_section == "advanced"
    app.show("home")


@needs_display
def test_recents_flow(app, tmp_path):
    p = tmp_path / "somefile.pdf"
    p.write_bytes(b"%PDF-1.4\n%%EOF\n")
    app.remember_input(str(p))
    _pump(app, 0.2)
    texts = [w.cget("text") for w in app._recent_frame.winfo_children()
             if hasattr(w, "cget")]
    assert any(str(p) in t for t in texts)


@needs_display
def test_both_themes_no_crash(app):
    for theme in ("light", "dark"):
        app.set_theme(theme)
        app.update_idletasks()
        app.update()
        assert app.theme == theme
