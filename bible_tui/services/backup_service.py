"""Protecting the half of the database you can't re-download.

Scripture, Strong's and the commentaries can always be rebuilt by re-running
the import. Bookmarks, notes, highlights, reading plans and settings cannot -
they only exist here. So there are two ways out:

* a **snapshot**, a byte-exact copy of the whole database taken through
  SQLite's own backup API, which is safe to run while the app is open; and
* an **archive**, a JSON file holding only the personal tables, which
  survives a schema change and can be read by anything.

Restoring an archive merges by default, so importing the same file twice
doesn't duplicate a single note.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

#: The tables that hold work a person did, in dependency order - plans
#: before their entries, so a restore never inserts an orphan.
PERSONAL_TABLES: tuple[str, ...] = (
    "bookmarks",
    "notes",
    "highlights",
    "reading_plans",
    "plan_entries",
    "settings",
    "last_position",
)

ARCHIVE_VERSION = 1

DEFAULT_BACKUP_DIR = Path.home() / "Documents"


class BackupError(RuntimeError):
    """Raised when a backup or restore could not be completed."""


@dataclass(frozen=True)
class IntegrityReport:
    """The result of checking the database over."""

    ok: bool
    problems: tuple[str, ...] = ()

    def summary(self) -> str:
        if self.ok:
            return "Database is healthy"
        return f"{len(self.problems)} problem(s): " + "; ".join(self.problems[:3])


@dataclass
class BackupService:
    conn: sqlite3.Connection

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------

    def check(self, thorough: bool = False) -> IntegrityReport:
        """Verify the database.

        `quick_check` skips the index cross-referencing that makes a full
        `integrity_check` slow on an 80MB file - fast enough to run on every
        launch, and it still catches real corruption.
        """
        pragma = "integrity_check" if thorough else "quick_check"
        problems: list[str] = []
        try:
            rows = self.conn.execute(f"PRAGMA {pragma}").fetchall()
            problems += [r[0] for r in rows if r[0] != "ok"]
            problems += [
                f"orphaned row in {r[0]} (references {r[2]})"
                for r in self.conn.execute("PRAGMA foreign_key_check").fetchall()
            ]
        except sqlite3.Error as error:
            return IntegrityReport(False, (str(error),))
        return IntegrityReport(not problems, tuple(problems))

    # ------------------------------------------------------------------
    # Snapshot - the whole database, byte for byte
    # ------------------------------------------------------------------

    def snapshot(self, path: Path) -> Path:
        """Copy the entire database to `path`.

        Uses SQLite's online backup API rather than a file copy, so it is
        safe while the app is running and mid-transaction.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            destination = sqlite3.connect(path)
            try:
                with destination:
                    self.conn.backup(destination)
            finally:
                destination.close()
        except (OSError, sqlite3.Error) as error:
            raise BackupError(str(error)) from error
        return path

    def restore_snapshot(self, path: Path) -> None:
        """Replace this database's contents with a snapshot's.

        The snapshot is verified before anything is overwritten, so a
        truncated or unrelated file fails loudly instead of destroying the
        database it was meant to rescue.
        """
        if not path.exists():
            raise BackupError(f"no such file: {path}")
        try:
            source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.Error as error:
            raise BackupError(f"not a readable database: {error}") from error
        try:
            report = BackupService(source).check()
            if not report.ok:
                raise BackupError(f"snapshot is damaged - {report.summary()}")
            if not source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='verses'"
            ).fetchone():
                raise BackupError("snapshot does not look like a bible database")
            with self.conn:
                source.backup(self.conn)
        except sqlite3.Error as error:
            raise BackupError(str(error)) from error
        finally:
            source.close()

    # ------------------------------------------------------------------
    # Archive - personal tables only, as JSON
    # ------------------------------------------------------------------

    def archive(self) -> dict:
        """Everything a person made, as plain JSON-ready data."""
        payload: dict = {
            "format": "bible-tui-personal-data",
            "version": ARCHIVE_VERSION,
            "exported_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tables": {},
        }
        for table in PERSONAL_TABLES:
            try:
                rows = self.conn.execute(f"SELECT * FROM {table}").fetchall()
            except sqlite3.Error:
                continue  # a table this build doesn't have yet
            payload["tables"][table] = [dict(row) for row in rows]
        return payload

    def write_archive(self, path: Path) -> Path:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self.archive(), indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as error:
            raise BackupError(str(error)) from error
        return path

    def read_archive(self, path: Path, replace: bool = False) -> dict[str, int]:
        """Load an archive back in; returns rows restored per table.

        Merging is the default: rows are inserted with OR IGNORE so the
        UNIQUE constraints on bookmarks and highlights quietly absorb
        anything already present. `replace=True` empties each table first,
        for restoring onto a machine that should mirror the source exactly.
        """
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise BackupError(f"could not read archive: {error}") from error

        if not isinstance(payload, dict) or payload.get("format") != "bible-tui-personal-data":
            raise BackupError("not a bible-tui personal data archive")

        tables = payload.get("tables")
        if not isinstance(tables, dict):
            raise BackupError("archive contains no tables")

        restored: dict[str, int] = {}
        try:
            with self.conn:
                for table in PERSONAL_TABLES:
                    rows = tables.get(table)
                    if not isinstance(rows, list) or not rows:
                        continue
                    if replace:
                        self.conn.execute(f"DELETE FROM {table}")
                    restored[table] = self._insert(table, rows)
        except sqlite3.Error as error:
            raise BackupError(str(error)) from error
        return restored

    def _insert(self, table: str, rows: list[dict]) -> int:
        """Insert rows, ignoring any column the current schema dropped."""
        known = {
            r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        inserted = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            columns = [c for c in row if c in known]
            if not columns:
                continue
            placeholders = ", ".join("?" for _ in columns)
            self.conn.execute(
                f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                [row[c] for c in columns],
            )
            inserted += 1
        return inserted


def default_snapshot_path(directory: Path | None = None) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return (directory or DEFAULT_BACKUP_DIR) / f"bible-backup-{stamp}.db"


def default_archive_path(directory: Path | None = None) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return (directory or DEFAULT_BACKUP_DIR) / f"bible-personal-{stamp}.json"
