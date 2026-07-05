"""Text-to-speech read-aloud.

macOS ships a synthesizer (``say``) with no extra dependency to install.
Every other platform needs one picked and installed by hand - ``pyttsx3``,
``espeak``, a cloud API - and this project doesn't choose one for you yet,
so :func:`speak` fails loudly there instead of silently doing nothing.
"""

from __future__ import annotations

import platform
import subprocess
from typing import Callable


class TTSUnavailable(RuntimeError):
    """Raised when no text-to-speech backend is available on this platform."""


def is_available() -> bool:
    return platform.system() == "Darwin"


def speak(text: str, *, runner: Callable[[list[str]], object] = subprocess.Popen) -> object:
    """Start reading *text* aloud, returning the running process.

    Runs asynchronously (``Popen`` by default, not ``run``) so the UI isn't
    blocked while a whole chapter is read aloud; the caller terminates the
    returned process to stop early. *runner* is swappable so callers (and
    tests) never have to actually shell out to ``say``.
    """
    if not is_available():
        raise TTSUnavailable(
            "Text-to-speech needs macOS's `say` command; no backend is configured "
            "for this platform yet."
        )
    return runner(["say", text])
