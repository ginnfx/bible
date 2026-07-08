"""System clipboard access with an OSC 52 fallback.

Two paths are attempted, and either one succeeding counts as a copy:

* the platform's native helper (``pbcopy``, ``wl-copy``, ``xclip``, ``clip``),
  which is what a local terminal session wants; and
* an OSC 52 escape written to the terminal, which is what makes copying work
  over SSH or on a headless box where no native helper exists.

Both are stdlib-only, so the app keeps its two-dependency install.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys

#: Native clipboard helpers, in the order they're tried. The first entry
#: whose binary exists on PATH is used.
_NATIVE_COMMANDS: list[list[str]] = [
    ["pbcopy"],  # macOS
    ["wl-copy"],  # Wayland
    ["xclip", "-selection", "clipboard"],  # X11
    ["xsel", "--clipboard", "--input"],  # X11 alternative
    ["clip"],  # Windows
]


class ClipboardError(RuntimeError):
    """Raised when no clipboard path succeeded."""


def copy(text: str) -> None:
    """Copy ``text`` to the system clipboard.

    Raises ``ClipboardError`` only when both the native helper and OSC 52
    fail, so a machine with neither still reports honestly instead of
    silently dropping the copy.
    """
    native_ok = _copy_native(text)
    osc52_ok = _copy_osc52(text)
    if not (native_ok or osc52_ok):
        raise ClipboardError("clipboard unavailable")


def _copy_native(text: str) -> bool:
    for command in _NATIVE_COMMANDS:
        if shutil.which(command[0]) is None:
            continue
        try:
            subprocess.run(command, input=text.encode("utf-8"), check=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            continue
        return True
    return False


def _copy_osc52(text: str) -> bool:
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    try:
        stream = sys.__stdout__
        if stream is None:
            return False
        stream.write(f"\x1b]52;c;{payload}\x07")
        stream.flush()
    except (OSError, ValueError):
        return False
    return True


def osc52_sequence(text: str) -> str:
    """The raw OSC 52 escape for ``text`` - exposed for tests."""
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"\x1b]52;c;{payload}\x07"
