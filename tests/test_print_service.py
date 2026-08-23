"""Printing - a thin subprocess wrapper around CUPS's ``lp``. The only logic
worth testing is availability detection and that it fails loudly rather
than silently doing nothing where no print command exists.
"""

from __future__ import annotations

import pytest

from bible_tui.models.verse import Verse
from bible_tui.services import print_service

VERSE = Verse(
    id=1, book_id=43, book_name="John", chapter=3, verse=16,
    text="For God so loved the world.",
)


def test_available_when_lp_is_on_path(monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: "/usr/bin/lp")
    assert print_service.is_available() is True


def test_unavailable_without_lp(monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: None)
    assert print_service.is_available() is False


def test_print_verses_shells_out_to_lp(monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: "/usr/bin/lp")
    calls = []

    def fake_runner(args, **kwargs):
        calls.append((args, kwargs))

    print_service.print_verses([VERSE], "KJV", runner=fake_runner)
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ["lp"]
    assert "John 3:16" in kwargs["input"]


def test_printing_raises_without_lp(monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: None)
    with pytest.raises(print_service.PrintUnavailable):
        print_service.print_verses([VERSE], "KJV")


def test_printing_nothing_raises(monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: "/usr/bin/lp")
    with pytest.raises(print_service.PrintUnavailable):
        print_service.print_verses([], "KJV")
