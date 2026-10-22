"""Console output that survives a non-UTF-8 terminal.

Windows' console often defaults to cp1252, which cannot encode Persian text.
Management commands that print Persian would crash with a UnicodeEncodeError,
so they write through this helper instead.
"""

from __future__ import annotations

import sys


def safe(text: str) -> str:
    """The text, with anything the terminal cannot show replaced."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
        return text
    except (UnicodeEncodeError, LookupError):
        return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def write(stream, text: str) -> None:
    """Write a line, replacing what the terminal cannot show."""
    stream.write(safe(text) + "\n")
