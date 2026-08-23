"""Seeding a fresh install from a bundled database - the mechanism a
packaged build uses to skip `import-data` entirely on first run."""

from __future__ import annotations

from bible_tui.data import database


def test_no_seed_means_nothing_to_find(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "_bundle_dir", lambda: tmp_path)
    assert database.seed_db_path() is None


def test_a_bundled_seed_is_found(monkeypatch, tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "bible.db").write_bytes(b"fake db")
    monkeypatch.setattr(database, "_bundle_dir", lambda: tmp_path)
    assert database.seed_db_path() == seed_dir / "bible.db"


def test_ensure_seeded_copies_the_bundled_db_into_a_missing_path(monkeypatch, tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "bible.db").write_bytes(b"fake db")
    monkeypatch.setattr(database, "_bundle_dir", lambda: tmp_path)

    target = tmp_path / "config" / "bible.db"
    database.ensure_seeded(target)
    assert target.read_bytes() == b"fake db"


def test_ensure_seeded_never_overwrites_an_existing_database(monkeypatch, tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "bible.db").write_bytes(b"fake seed")
    monkeypatch.setattr(database, "_bundle_dir", lambda: tmp_path)

    target = tmp_path / "config" / "bible.db"
    target.parent.mkdir()
    target.write_bytes(b"already here")

    database.ensure_seeded(target)
    assert target.read_bytes() == b"already here"


def test_ensure_seeded_is_a_no_op_when_nothing_is_bundled(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "_bundle_dir", lambda: tmp_path)
    target = tmp_path / "config" / "bible.db"
    database.ensure_seeded(target)
    assert not target.exists()
