"""Printing - CUPS's ``lp`` on macOS/Linux, the shell's "print" verb on
Windows. The logic worth testing is which path each platform takes and
that it fails loudly rather than silently doing nothing where no print
command exists.
"""

from __future__ import annotations

import pytest

from bible_tui.models.verse import Verse
from bible_tui.services import print_service

VERSE = Verse(
    id=1, book_id=43, book_name="John", chapter=3, verse=16,
    text="For God so loved the world.",
)


@pytest.fixture
def on_unix(monkeypatch):
    monkeypatch.setattr(print_service.platform, "system", lambda: "Linux")


@pytest.fixture
def on_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(print_service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(print_service.tempfile, "gettempdir", lambda: str(tmp_path))


def test_available_when_lp_is_on_path(on_unix, monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: "/usr/bin/lp")
    assert print_service.is_available() is True


def test_unavailable_without_lp(on_unix, monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: None)
    assert print_service.is_available() is False


def test_print_verses_shells_out_to_lp(on_unix, monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: "/usr/bin/lp")
    calls = []

    def fake_runner(args, **kwargs):
        calls.append((args, kwargs))

    print_service.print_verses([VERSE], "KJV", runner=fake_runner)
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ["lp"]
    assert "John 3:16" in kwargs["input"]


def test_printing_raises_without_lp(on_unix, monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: None)
    with pytest.raises(print_service.PrintUnavailable):
        print_service.print_verses([VERSE], "KJV")


def test_printing_nothing_raises(on_unix, monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: "/usr/bin/lp")
    with pytest.raises(print_service.PrintUnavailable):
        print_service.print_verses([], "KJV")


def test_available_on_windows_without_lp(on_windows, monkeypatch):
    monkeypatch.setattr(print_service.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(print_service.os, "startfile", lambda *a: None, raising=False)
    assert print_service.is_available() is True


def test_windows_prints_a_utf8_text_file_through_the_print_verb(on_windows):
    started = []

    print_service.print_verses(
        [VERSE], "KJV", "John 3", starter=lambda path, verb: started.append((path, verb))
    )

    assert len(started) == 1
    path, verb = started[0]
    assert verb == "print"
    assert path.endswith(".txt")
    # A BOM so Notepad (the default handler for .txt) reads it as UTF-8.
    with open(path, "rb") as handle:
        raw = handle.read()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "John 3:16" in raw.decode("utf-8-sig")


def test_windows_print_failure_is_reported_not_raised_raw(on_windows):
    def no_printer(path, verb):
        raise OSError("No application is associated with the specified file")

    with pytest.raises(print_service.PrintUnavailable):
        print_service.print_verses([VERSE], "KJV", starter=no_printer)


def test_windows_prunes_print_files_older_than_a_day(on_windows, tmp_path):
    stale = tmp_path / "bible-print-old.txt"
    stale.write_text("old")
    two_days_ago = print_service.time.time() - 2 * 24 * 60 * 60
    print_service.os.utime(stale, (two_days_ago, two_days_ago))
    unrelated = tmp_path / "someone-elses.txt"
    unrelated.write_text("keep")
    print_service.os.utime(unrelated, (two_days_ago, two_days_ago))

    print_service.print_verses([VERSE], "KJV", starter=lambda path, verb: None)

    assert not stale.exists()
    assert unrelated.exists()
    assert len(list(tmp_path.glob("bible-print-*.txt"))) == 1  # just today's
