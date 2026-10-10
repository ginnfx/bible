"""Text-to-speech read-aloud.

``speak`` is a thin subprocess wrapper; the logic worth testing is which
backend each platform picks, how the text reaches it, and that it fails
loudly rather than silently doing nothing where no backend exists.
"""

from __future__ import annotations

import pytest

from bible_tui.services import tts_service


def _on(monkeypatch, system: str, installed: set[str]) -> None:
    monkeypatch.setattr(tts_service.platform, "system", lambda: system)
    monkeypatch.setattr(
        tts_service.shutil, "which", lambda name: f"/bin/{name}" if name in installed else None
    )


class FakeStdin:
    def __init__(self, broken: bool = False) -> None:
        self.written = b""
        self.closed = False
        self.broken = broken

    def write(self, data: bytes) -> None:
        if self.broken:
            raise BrokenPipeError("the synthesizer exited early")
        self.written += data

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(self, broken: bool = False) -> None:
        self.stdin = FakeStdin(broken)


def test_available_on_macos_with_say(monkeypatch):
    _on(monkeypatch, "Darwin", {"say"})
    assert tts_service.is_available() is True


def test_available_on_windows_with_powershell(monkeypatch):
    _on(monkeypatch, "Windows", {"powershell"})
    assert tts_service.is_available() is True


def test_available_on_linux_with_espeak_ng(monkeypatch):
    _on(monkeypatch, "Linux", {"espeak-ng"})
    assert tts_service.is_available() is True


def test_unavailable_on_linux_without_espeak(monkeypatch):
    _on(monkeypatch, "Linux", set())
    assert tts_service.is_available() is False


def test_linux_unavailable_reason_names_the_package_to_install(monkeypatch):
    _on(monkeypatch, "Linux", set())
    assert "espeak-ng" in tts_service.unavailable_reason()


def test_speak_invokes_say_with_the_text(monkeypatch):
    _on(monkeypatch, "Darwin", {"say"})
    calls = []

    def fake_runner(args, **kwargs):
        calls.append(args)
        return "a-process-handle"

    result = tts_service.speak("For God so loved the world", runner=fake_runner)
    assert calls == [["say", "For God so loved the world"]]
    assert result == "a-process-handle"


def test_linux_falls_back_to_plain_espeak(monkeypatch):
    _on(monkeypatch, "Linux", {"espeak"})
    calls = []
    tts_service.speak("In the beginning", runner=lambda args, **kw: calls.append(args))
    assert calls == [["espeak", "In the beginning"]]


def test_windows_pipes_the_text_through_stdin_as_utf8(monkeypatch):
    # A long chapter would blow past Windows' command-line length limit,
    # and non-ASCII text would be mangled by the console code page, so the
    # text goes in on stdin as UTF-8 rather than as an argument.
    _on(monkeypatch, "Windows", {"powershell"})
    process = FakeProcess()
    calls = []

    def fake_runner(args, **kwargs):
        calls.append((args, kwargs))
        return process

    result = tts_service.speak("João 3:16 — amor", runner=fake_runner)
    args, kwargs = calls[0]
    assert args[0] == "powershell"
    assert "System.Speech" in args[-1]
    assert "João 3:16 — amor" not in " ".join(args)
    assert kwargs["stdin"] == tts_service.subprocess.PIPE
    # PowerShell's own error text must never be painted over the TUI.
    assert kwargs["stdout"] == kwargs["stderr"] == tts_service.subprocess.DEVNULL
    assert process.stdin.written.decode("utf-8") == "João 3:16 — amor"
    assert process.stdin.closed is True
    assert result is process


def test_windows_synthesizer_dying_early_is_reported_not_crashing(monkeypatch):
    _on(monkeypatch, "Windows", {"powershell"})
    with pytest.raises(tts_service.TTSUnavailable):
        tts_service.speak("text", runner=lambda args, **kw: FakeProcess(broken=True))


def test_speak_raises_without_a_backend(monkeypatch):
    _on(monkeypatch, "Linux", set())
    with pytest.raises(tts_service.TTSUnavailable):
        tts_service.speak("text")
