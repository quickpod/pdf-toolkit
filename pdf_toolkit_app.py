#!/usr/bin/env python3
r"""PDF Toolkit unified entry point (this is what gets built into PDFToolkit.exe).

  PDFToolkit.exe                 -> launch the GUI
  PDFToolkit.exe <command> ...   -> run the CLI (same as `python -m pdftoolkit ...`)

100% open source, fully offline. Nothing is uploaded anywhere.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    argv = sys.argv[1:]
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
