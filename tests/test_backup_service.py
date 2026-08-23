from __future__ import annotations

import json
import sqlite3

import pytest

from bible_tui.services.backup_service import (
    BackupError,
    BackupService,
    default_archive_path,
    default_snapshot_path,
)


@pytest.fixture
def annotated(repo):
    """A database with a bookmark, a note and a highlight already in it."""
    repo.add_bookmark(43, 3, 16, "the famous one")
    repo.add_note(43, 3, 16, "Nicodemus by night.")
    repo.set_highlight(43, 3, 16, "yellow")
    repo.set_setting("search_history", ["love"])
    return repo


@pytest.fixture
def service(annotated):
    return BackupService(annotated.conn)


# --------------------------------------------------------------------------
# Integrity
# --------------------------------------------------------------------------


def test_healthy_database_passes_the_check(service):
    report = service.check()
    assert report.ok
    assert report.problems == ()
    assert "healthy" in report.summary().lower()


def test_thorough_check_also_passes(service):
    assert service.check(thorough=True).ok


def test_closed_connection_is_reported_not_raised(annotated):
    conn = annotated.conn
    service = BackupService(conn)
    conn.close()
    report = service.check()
    assert not report.ok
    assert report.problems


# --------------------------------------------------------------------------
# Snapshots
# --------------------------------------------------------------------------


def test_snapshot_round_trips(service, tmp_path):
    path = service.snapshot(tmp_path / "copy.db")
    assert path.exists()

    copy = sqlite3.connect(path)
    try:
        assert copy.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0] == 1
        assert copy.execute("SELECT COUNT(*) FROM verses").fetchone()[0] > 0
    finally:
        copy.close()


def test_snapshot_creates_missing_directories(service, tmp_path):
    path = service.snapshot(tmp_path / "nested" / "deeper" / "copy.db")
    assert path.exists()


def test_restore_brings_back_deleted_work(service, annotated, tmp_path):
    path = service.snapshot(tmp_path / "before.db")
    annotated.remove_bookmark(43, 3, 16)
    assert annotated.list_bookmarks() == []

    service.restore_snapshot(path)
    assert len(annotated.list_bookmarks()) == 1


def test_restore_refuses_a_missing_file(service, tmp_path):
    with pytest.raises(BackupError, match="no such file"):
        service.restore_snapshot(tmp_path / "nowhere.db")


def test_restore_refuses_an_unrelated_database(service, tmp_path):
    other = tmp_path / "other.db"
    conn = sqlite3.connect(other)
    conn.execute("CREATE TABLE recipes (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    with pytest.raises(BackupError, match="does not look like"):
        service.restore_snapshot(other)


def test_restore_refuses_a_file_that_is_not_a_database(service, tmp_path):
    junk = tmp_path / "notes.txt"
    junk.write_text("this is not a database")
    with pytest.raises(BackupError):
        service.restore_snapshot(junk)


# --------------------------------------------------------------------------
# Archives
# --------------------------------------------------------------------------


def test_archive_holds_personal_tables_only(service):
    payload = service.archive()
    assert payload["format"] == "bible-tui-personal-data"
    assert "bookmarks" in payload["tables"]
    assert "verses" not in payload["tables"]
    assert "books" not in payload["tables"]


def test_archive_captures_the_work(service):
    tables = service.archive()["tables"]
    assert tables["bookmarks"][0]["label"] == "the famous one"
    assert tables["notes"][0]["body"] == "Nicodemus by night."
    assert tables["highlights"][0]["color"] == "yellow"


def test_archive_round_trips_through_a_file(service, annotated, tmp_path):
    path = service.write_archive(tmp_path / "personal.json")
    annotated.remove_bookmark(43, 3, 16)

    restored = service.read_archive(path)
    assert restored["bookmarks"] == 1
    assert len(annotated.list_bookmarks()) == 1


def test_importing_the_same_archive_twice_does_not_duplicate(service, annotated, tmp_path):
    path = service.write_archive(tmp_path / "personal.json")
    service.read_archive(path)
    service.read_archive(path)
    assert len(annotated.list_bookmarks()) == 1


def test_replace_mode_mirrors_the_archive_exactly(service, annotated, tmp_path):
    path = service.write_archive(tmp_path / "personal.json")
    annotated.add_bookmark(1, 1, 1, "added later")
    assert len(annotated.list_bookmarks()) == 2

    service.read_archive(path, replace=True)
    assert len(annotated.list_bookmarks()) == 1


def test_unknown_columns_are_dropped_rather_than_crashing(service, annotated, tmp_path):
    path = tmp_path / "future.json"
    payload = service.archive()
    for row in payload["tables"]["bookmarks"]:
        row["mood"] = "hopeful"
    annotated.remove_bookmark(43, 3, 16)
    path.write_text(json.dumps(payload))

    assert service.read_archive(path)["bookmarks"] == 1
    assert len(annotated.list_bookmarks()) == 1


def test_a_foreign_json_file_is_refused(service, tmp_path):
    path = tmp_path / "foreign.json"
    path.write_text(json.dumps({"format": "some-other-app", "tables": {}}))
    with pytest.raises(BackupError):
        service.read_archive(path)


def test_an_unreadable_file_is_refused(service, tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json at all")
    with pytest.raises(BackupError):
        service.read_archive(path)


# --------------------------------------------------------------------------
# Default paths
# --------------------------------------------------------------------------


def test_default_paths_are_dated_and_distinct(tmp_path):
    snapshot = default_snapshot_path(tmp_path)
    archive = default_archive_path(tmp_path)
    assert snapshot.parent == tmp_path
    assert snapshot.name.startswith("bible-backup-") and snapshot.suffix == ".db"
    assert archive.name.startswith("bible-personal-") and archive.suffix == ".json"
