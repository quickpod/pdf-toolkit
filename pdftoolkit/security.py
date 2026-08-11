"""Encryption, decryption and permission control via pikepdf (AES-256)."""

from __future__ import annotations

import os

import pikepdf

from .common import ensure_parent_dir
from .errors import PdfToolkitError


def protect(
    input,
    output,
    user_password="",
    owner_password=None,
    allow_print=True,
    allow_copy=True,
    allow_modify=True,
    allow_annotate=True,
):
    """Encrypt *input* with AES-256 (PDF 2.0, R=6).

    :param user_password: password required to *open* the document (``""`` =
        open freely but still permission-restricted).
    :param owner_password: password granting full rights; defaults to
        *user_password* when ``None``.
    :param allow_print/allow_copy/allow_modify/allow_annotate: permission flags.
    :returns: *output* path.
    """
    if not os.path.exists(input):
        raise PdfToolkitError(f"input file not found: {input}")
    owner = owner_password if owner_password is not None else user_password
    ensure_parent_dir(output)

    perms = pikepdf.Permissions(
        accessibility=True,
        extract=allow_copy,
        modify_annotation=allow_annotate,
        modify_assembly=allow_modify,
        modify_form=allow_modify,
        modify_other=allow_modify,
        print_lowres=allow_print,
        print_highres=allow_print,
    )
    try:
        pdf = pikepdf.open(input)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"could not open PDF {input!r}: {exc}") from exc
    try:
        enc = pikepdf.Encryption(owner=owner, user=user_password, R=6, allow=perms)
        pdf.save(output, encryption=enc)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"encryption failed: {exc}") from exc
    finally:
        pdf.close()
    return output


def unprotect(input, output, password):
    """Decrypt *input* using *password*, writing an unencrypted *output*.

    :raises PdfToolkitError: if the password is wrong or the file is unreadable.
    :returns: *output* path.
    """
    if not os.path.exists(input):
        raise PdfToolkitError(f"input file not found: {input}")
    ensure_parent_dir(output)
    try:
        pdf = pikepdf.open(input, password=password)
    except pikepdf.PasswordError as exc:
        raise PdfToolkitError("incorrect password") from exc
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"could not open PDF {input!r}: {exc}") from exc
    try:
        pdf.save(output)
    except Exception as exc:  # noqa: BLE001
        raise PdfToolkitError(f"decryption save failed: {exc}") from exc
    finally:
        pdf.close()
    return output


def is_encrypted(input):
    """Return True if *input* is encrypted (no password needed to check)."""
    from .common import read_pdf

    return bool(read_pdf(input).is_encrypted)
