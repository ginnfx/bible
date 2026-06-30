"""Build a content-only seed database for packaged builds.

Takes a real, in-use ``bible.db`` and strips every user-data table -
bookmarks, notes, highlights, reading history, settings, everything a
reader has personally added - leaving only the Bible text and reference
data (translations, verses, Strong's, cross-references, commentary).
That's what a packaged build ships so a first run has real text without
running `import-data`, without also shipping whoever built it their own
reading history.

Usage:
    python scripts/build_seed_db.py [source_db] [dest_db]

Defaults to the current profile's database as the source, and
``packaging/seed/bible.db`` as the destination.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

#: Tables that hold a reader's own data rather than Bible content - every
#: one of these is dropped from the seed. Kept as an explicit allowlist
#: rather than "everything except content tables" so a future new table
#: defaults to being stripped (privacy-safe) unless someone deliberately
#: adds it to `CONTENT_TABLES` below.
USER_DATA_TABLES = (
    "bookmarks",
    "notes",
    "highlights",
    "bookmark_folders",
    "tags",
    "verse_tags",
    "note_tags",
    "favourites",
    "reading_lists",
    "reading_list_items",
    "reading_plans",
    "plan_entries",
    "settings",
    "last_position",
    "reading_events",
)

CONTENT_TABLES = (
    "translations",
    "books",
    "verses",
    "strongs",
    "verse_strongs",
    "cross_references",
    "commentaries",
)


def build_seed(source: Path, dest: Path) -> None:
    if not source.exists():
        raise SystemExit(f"Source database not found: {source}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()

    shutil.copy(source, dest)
    conn = sqlite3.connect(dest)
    try:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        stripped = []
        for table in USER_DATA_TABLES:
            if table in tables:
                conn.execute(f"DELETE FROM {table}")
                stripped.append(table)
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()

    print(f"Seed database written to {dest} ({dest.stat().st_size / 1_048_576:.1f} MB).")
    print(f"Stripped: {', '.join(stripped)}")
    missing_content = [t for t in CONTENT_TABLES if t not in tables]
    if missing_content:
        print(f"Warning: expected content tables missing from source: {missing_content}")


if __name__ == "__main__":
    default_source = Path.home() / ".config" / "bible-tui" / "bible.db"
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else default_source
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("packaging/seed/bible.db")
    build_seed(source, dest)
