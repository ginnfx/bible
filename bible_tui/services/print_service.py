"""Printing - CUPS's ``lp`` on macOS and most Linux distributions, and the
shell's "print" verb on Windows.

Windows has no ``lp``; the native equivalent of "send this text to the
default printer" is handing a ``.txt`` file to whatever is registered to
print it (Notepad, out of the box). Same "fail loudly, don't fake it"
precedent as ``tts_service.py``: when neither path exists, the reader is
told plainly rather than the print silently vanishing.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..models.verse import Verse
from . import export_service


#: Print files older than this are long since spooled and safe to delete.
_PRINT_FILE_MAX_AGE_SECONDS = 24 * 60 * 60


class PrintUnavailable(RuntimeError):
    """Raised when no print path is available, or the print couldn't start."""


def _is_windows() -> bool:
    return platform.system() == "Windows"


def is_available() -> bool:
    if _is_windows():
        return hasattr(os, "startfile")
    return shutil.which("lp") is not None


def print_verses(
    verses: list[Verse],
    translation_code: str,
    title: str = "",
    *,
    runner: Callable[..., object] = subprocess.run,
    starter: Callable[[str, str], object] | None = None,
) -> None:
    """Send *verses* to the default printer.

    Renders through `export_service`'s plain-text writer, so a printed page
    looks exactly like a plain-text export - one less format to maintain.
    *runner* (``lp``) and *starter* (``os.startfile``) are swappable so
    tests never reach a real printer.
    """
    if not verses:
        raise PrintUnavailable("nothing to print")
    text = export_service.render(verses, export_service.TEXT, translation_code, title)
    if _is_windows():
        _print_on_windows(text, starter or getattr(os, "startfile", None))
        return
    if not is_available():
        raise PrintUnavailable(
            "Printing needs a CUPS `lp` command; not available on this system."
        )
    runner(["lp"], input=text, text=True, check=True)


def _print_on_windows(text: str, starter: Callable[[str, str], object] | None) -> None:
    if starter is None:
        raise PrintUnavailable("Printing isn't available on this system.")
    # The handler reads the file after startfile returns, so it can't be
    # deleted here; a timestamped name avoids collisions, and the next print
    # sweeps up any left over from earlier days.
    temp_dir = Path(tempfile.gettempdir())
    _prune_old_print_files(temp_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = temp_dir / f"bible-print-{stamp}.txt"
    try:
        path.write_text(text, encoding="utf-8-sig")
        starter(str(path), "print")
    except OSError as error:
        raise PrintUnavailable(f"Couldn't print: {error}") from error


def _prune_old_print_files(temp_dir: Path) -> None:
    cutoff = time.time() - _PRINT_FILE_MAX_AGE_SECONDS
    for old in temp_dir.glob("bible-print-*.txt"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            continue  # in use or already gone - next print tries again
