"""Text-to-speech read-aloud.

``speak`` is a thin subprocess wrapper; the only logic worth testing is
which platforms it will run on and that it fails loudly rather than
silently doing nothing where no backend exists.
"""

from __future__ import annotations

import pytest

from bible_tui.services import tts_service


def test_available_on_macos(monkeypatch):
    monkeypatch.setattr(tts_service.platform, "system", lambda: "Darwin")
    assert tts_service.is_available() is True


def test_unavailable_elsewhere(monkeypatch):
    monkeypatch.setattr(tts_service.platform, "system", lambda: "Linux")
    assert tts_service.is_available() is False


def test_speak_invokes_say_with_the_text(monkeypatch):
    monkeypatch.setattr(tts_service.platform, "system", lambda: "Darwin")
    calls = []

    def fake_runner(args):
        calls.append(args)
        return "a-process-handle"

    result = tts_service.speak("For God so loved the world", runner=fake_runner)
    assert calls == [["say", "For God so loved the world"]]
    assert result == "a-process-handle"


def test_speak_raises_without_a_backend(monkeypatch):
    monkeypatch.setattr(tts_service.platform, "system", lambda: "Linux")
    with pytest.raises(tts_service.TTSUnavailable):
        tts_service.speak("text")
