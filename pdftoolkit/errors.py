"""Error types for pdftoolkit."""


class PdfToolkitError(Exception):
    """Raised for any recoverable failure in a pdftoolkit operation.

    All public functions raise this (and only this) on failure so callers
    -- including the CLI and a future GUI -- have a single exception to catch.
    """
