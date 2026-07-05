"""Printing - shells out to CUPS's ``lp``, present on macOS and most Linux
distributions.

Same "fail loudly, don't fake it" precedent as ``tts_service.py``'s
macOS-only ``say`` backend: there's no cross-platform way to print from a
terminal app without picking a print stack, so this checks for `lp` and
tells the reader plainly when it isn't there rather than pretending
Windows is supported.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Callable

from ..models.verse import Verse
from . import export_service


class PrintUnavailable(RuntimeError):
    """Raised when no `lp`-compatible print command is on PATH."""


def is_available() -> bool:
    return shutil.which("lp") is not None


def print_verses(
    verses: list[Verse],
    translation_code: str,
    title: str = "",
    *,
    runner: Callable[..., object] = subprocess.run,
) -> None:
    """Send *verses* to the default printer via `lp`.

    Renders through `export_service`'s plain-text writer, so a printed page
    looks exactly like a plain-text export - one less format to maintain.
    """
    if not is_available():
        raise PrintUnavailable(
            "Printing needs a CUPS `lp` command; not available on this system."
        )
    if not verses:
        raise PrintUnavailable("nothing to print")
    text = export_service.render(verses, export_service.TEXT, translation_code, title)
    runner(["lp"], input=text, text=True, check=True)
