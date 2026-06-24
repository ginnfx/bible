from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _bundle_dir() -> Path:
    """Where bundled resources live: a packaging tool's extraction
    directory when frozen, the project root otherwise (this file is
    ``<root>/bible_tui/data/database.py``, three parents up).

    PyInstaller exposes its extraction directory directly as
    ``sys._MEIPASS``. Nuitka doesn't set an equivalent - but it does
    rewrite ``__file__`` for every compiled module to point at its real
    on-disk location inside the extraction directory, so the same
    parent-counting that finds the project root from source finds the
    extraction root under a frozen Nuitka build too.
    """
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))


def seed_db_path() -> Path | None:
    """A pre-populated database shipped alongside a packaged build, so a
    fresh install has real text to read without running `import-data`
    first. Not present when running from source - those installs already
    go through the normal import flow."""
    candidate = _bundle_dir() / "seed" / "bible.db"
    return candidate if candidate.exists() else None


def ensure_seeded(db_path: Path) -> None:
    """Copy the bundled seed database into place on a genuinely first run.

    Only acts when nothing is there yet - an existing database, even an
    empty schema-only one from a previous launch, is left alone rather than
    silently overwritten.
    """
    if db_path.exists():
        return
    seed = seed_db_path()
    if seed is None:
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(seed, db_path)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_seeded(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())
    _ensure_column(conn, "bookmarks", "folder_id", "INTEGER REFERENCES bookmark_folders(id)")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Add `column` to `table` if it isn't there yet.

    ALTER TABLE ADD COLUMN isn't idempotent the way CREATE TABLE IF NOT
    EXISTS is, so it can't be a statement inside schema.sql's executescript -
    every launch after the first against an already-migrated database would
    fail on it (and, since executescript runs as one script, abort every
    statement after it too).
    """
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
