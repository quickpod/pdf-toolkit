#!/usr/bin/env python3
r"""PDF Toolkit unified entry point (this is what gets built into PDFToolkit.exe).

  PDFToolkit.exe                 -> launch the GUI
  PDFToolkit.exe <command> ...   -> run the CLI (same as `python -m pdftoolkit ...`)

100% open source, fully offline. Nothing is uploaded anywhere.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Single-instance marker: the installer's AppMutex checks this to warn the
# user to close the app before install/uninstall. Harmless off Windows.
if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.kernel32.CreateMutexW(None, False, "QuickOpen.PDFToolkit")
    except Exception:
        pass



def _cli_commands():
    """Return the CLI's subcommand names (empty set if introspection fails)."""
    try:
        import argparse
        from pdftoolkit.__main__ import build_parser
        for action in build_parser()._actions:
            if isinstance(action, argparse._SubParsersAction):
                return set(action.choices)
    except Exception:
        pass
    return set()


def main():
    argv = sys.argv[1:]
    if (argv and not argv[0].startswith("-")
            and argv[0] not in _cli_commands() and os.path.exists(argv[0])):
        # Launched with a document path (desktop Exec %f / Explorer "Open
        # with"), not a CLI subcommand — show the GUI instead of dying with an
        # argparse usage error.
        argv = []
    if argv:
        # CLI mode — delegate to the pdftoolkit package's argparse entry point.
        from pdftoolkit import __main__ as cli
        if hasattr(cli, "main"):
            try:
                return cli.main(argv)
            except TypeError:
                sys.argv = ["pdftoolkit", *argv]
                return cli.main()
        sys.argv = ["pdftoolkit", *argv]
        import runpy
        runpy.run_module("pdftoolkit", run_name="__main__")
        return 0
    # GUI mode.
    from pdftoolkit import gui
    return gui.main() or 0


if __name__ == "__main__":
    sys.exit(main() or 0)
