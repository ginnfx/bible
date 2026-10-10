"""Text-to-speech read-aloud.

Every platform this ships for has a synthesizer that needs no Python
dependency: macOS's ``say``, Windows' built-in SAPI voices (reached through
PowerShell's ``System.Speech``), and ``espeak-ng``/``espeak`` on Linux -
the one case that usually needs a package installed by hand. Where none is
found, :func:`speak` fails loudly instead of silently doing nothing.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

#: Reads all of stdin as UTF-8 and speaks it with the default Windows voice.
#: Stdin rather than an argument: a long chapter would overrun the Windows
#: command-line length limit, and the console code page would mangle any
#: non-ASCII text passed on the command line. The raw stream is decoded
#: directly rather than by setting [Console]::InputEncoding, which would
#: change the code page of the console the TUI itself is running in.
_WINDOWS_SPEAK_SCRIPT = (
    "$text = (New-Object IO.StreamReader([Console]::OpenStandardInput(), "
    "[Text.Encoding]::UTF8)).ReadToEnd(); "
    "Add-Type -AssemblyName System.Speech; "
    "(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak($text)"
)


@dataclass(frozen=True)
class _Backend:
    command: tuple[str, ...]
    #: True when the text goes in on stdin; otherwise it's the last argument.
    reads_stdin: bool = False


_BACKENDS: dict[str, tuple[_Backend, ...]] = {
    "Darwin": (_Backend(("say",)),),
    "Windows": (
        _Backend(
            ("powershell", "-NoProfile", "-NonInteractive", "-Command", _WINDOWS_SPEAK_SCRIPT),
            reads_stdin=True,
        ),
    ),
    "Linux": (_Backend(("espeak-ng",)), _Backend(("espeak",))),
}

_UNAVAILABLE_REASONS = {
    "Linux": "Read-aloud needs espeak-ng - install it (e.g. `sudo apt install espeak-ng`).",
    "Windows": "Read-aloud needs Windows PowerShell, which wasn't found on PATH.",
    "Darwin": "Read-aloud needs macOS's `say` command, which wasn't found.",
}


class TTSUnavailable(RuntimeError):
    """Raised when no text-to-speech backend is available on this platform."""


def _find_backend() -> _Backend | None:
    for backend in _BACKENDS.get(platform.system(), ()):
        if shutil.which(backend.command[0]) is not None:
            return backend
    return None


def is_available() -> bool:
    return _find_backend() is not None


def unavailable_reason() -> str:
    """A one-line, reader-facing explanation of what's missing here."""
    return _UNAVAILABLE_REASONS.get(
        platform.system(), "Read-aloud isn't supported on this platform yet."
    )


def speak(text: str, *, runner: Callable[..., object] = subprocess.Popen) -> object:
    """Start reading *text* aloud, returning the running process.

    Runs asynchronously (``Popen`` by default, not ``run``) so the UI isn't
    blocked while a whole chapter is read aloud; the caller terminates the
    returned process to stop early. *runner* is swappable so callers (and
    tests) never have to actually shell out to a synthesizer.
    """
    backend = _find_backend()
    if backend is None:
        raise TTSUnavailable(unavailable_reason())
    # The synthesizer shares the TUI's terminal; anything it prints (a
    # missing voice, a policy error) would be painted over the screen.
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if not backend.reads_stdin:
        return runner([*backend.command, text], **quiet)
    process = runner(list(backend.command), stdin=subprocess.PIPE, **quiet)
    try:
        process.stdin.write(text.encode("utf-8"))
        process.stdin.close()
    except OSError as error:
        raise TTSUnavailable(f"Read-aloud stopped before it started: {error}") from error
    return process
