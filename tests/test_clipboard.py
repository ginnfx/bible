"""The OSC 52 path is what makes copying work over SSH, so its encoding is
pinned against the same vectors christ-cli tests."""

from __future__ import annotations

import pytest

from bible_tui import clipboard


@pytest.mark.parametrize(
    ("text", "encoded"),
    [
        ("", ""),
        ("f", "Zg=="),
        ("fo", "Zm8="),
        ("foo", "Zm9v"),
        ("foob", "Zm9vYg=="),
        ("fooba", "Zm9vYmE="),
        ("foobar", "Zm9vYmFy"),
        ("João 3:16", "Sm/Do28gMzoxNg=="),
    ],
)
def test_osc52_encodes_payload_as_base64(text, encoded):
    assert clipboard.osc52_sequence(text) == f"\x1b]52;c;{encoded}\x07"


def test_copy_succeeds_when_only_the_native_helper_works(monkeypatch):
    monkeypatch.setattr(clipboard, "_copy_native", lambda text: True)
    monkeypatch.setattr(clipboard, "_copy_osc52", lambda text: False)
    clipboard.copy("For God so loved the world")  # does not raise


def test_copy_succeeds_when_only_osc52_works(monkeypatch):
    # The headless/SSH case: no pbcopy, no xclip, but the terminal itself
    # can still take the escape sequence.
    monkeypatch.setattr(clipboard, "_copy_native", lambda text: False)
    monkeypatch.setattr(clipboard, "_copy_osc52", lambda text: True)
    clipboard.copy("For God so loved the world")


def test_copy_raises_only_when_both_paths_fail(monkeypatch):
    monkeypatch.setattr(clipboard, "_copy_native", lambda text: False)
    monkeypatch.setattr(clipboard, "_copy_osc52", lambda text: False)
    with pytest.raises(clipboard.ClipboardError):
        clipboard.copy("For God so loved the world")


def test_native_copy_skips_helpers_that_are_not_installed(monkeypatch):
    attempted: list[list[str]] = []

    monkeypatch.setattr(clipboard.shutil, "which", lambda name: None if name == "pbcopy" else "/usr/bin/" + name)
    monkeypatch.setattr(clipboard.subprocess, "run", lambda cmd, **kw: attempted.append(cmd))

    assert clipboard._copy_native("hello") is True
    assert attempted and attempted[0][0] != "pbcopy"


def test_native_copy_falls_through_when_a_helper_errors(monkeypatch):
    def explode(cmd, **kwargs):
        if cmd[0] == "pbcopy":
            raise OSError("no clipboard server")
        return None

    monkeypatch.setattr(clipboard.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(clipboard.subprocess, "run", explode)

    assert clipboard._copy_native("hello") is True
