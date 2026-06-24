from __future__ import annotations

import difflib
import json
import random
import sqlite3

from ..models.verse import Verse
from .book_aliases import normalise_book_query

#: How a bookmark list is sorted. Recency is the default because the last
#: thing you marked is usually the thing you came back for.
ORDER_RECENT = "recent"
ORDER_CANONICAL = "canonical"
ORDER_FOLDER = "folder"


class BibleRepository:
    """All SQL lives here. No business logic - that belongs in services/."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._vocabulary: dict[str, int] | None = None

    # ------------------------------------------------------------------
    # Books
    # ------------------------------------------------------------------

    def get_all_books(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM books ORDER BY book_num").fetchall()

    def get_book(self, book_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    def get_book_by_name_or_abbrev(self, query: str) -> sqlite3.Row | None:
        # Common spellings and short forms are folded onto the canonical name
        # first, so "Psalm", "jn" and "1cor" all resolve (see book_aliases).
        query = normalise_book_query(query).lower()
        return self.conn.execute(
            """
            SELECT * FROM books
            WHERE lower(name) = ? OR lower(abbreviation) = ? OR lower(osis_code) = ?
            LIMIT 1
            """,
            (query, query, query),
        ).fetchone()

    def suggest_books(self, query: str, limit: int = 3) -> list[str]:
        """Fuzzy fallback for typos, e.g. 'geenesis' -> ['Genesis']."""
        names = [row["name"] for row in self.get_all_books()]
        return difflib.get_close_matches(query.strip(), names, n=limit, cutoff=0.6)

    def chapter_count(self, book_id: int) -> int:
        row = self.conn.execute("SELECT chapter_count FROM books WHERE id = ?", (book_id,)).fetchone()
        return row["chapter_count"] if row else 0

    # ------------------------------------------------------------------
    # Verses
    # ------------------------------------------------------------------

    def get_verse(self, book_id: int, chapter: int, verse: int, translation_code: str) -> Verse | None:
        row = self.conn.execute(
            """
            SELECT v.id, v.chapter, v.verse, v.text, b.name AS book_name, b.id AS book_id
            FROM verses v
            JOIN books b ON v.book_id = b.id
            JOIN translations t ON v.translation_id = t.id
            WHERE v.book_id = ? AND v.chapter = ? AND v.verse = ? AND t.code = ?
            """,
            (book_id, chapter, verse, translation_code),
        ).fetchone()
        return Verse.from_row(row) if row else None

    def get_verse_in_every_translation(
        self, book_id: int, chapter: int, verse: int
    ) -> list[tuple[str, str, Verse | None]]:
        """One verse across every installed translation, in install order.

        Translations that lack the verse come back as None rather than being
        dropped, so the comparison shows the gap instead of hiding it.
        """
        translations = self.conn.execute(
            "SELECT code, name FROM translations ORDER BY id"
        ).fetchall()
        return [
            (t["code"], t["name"], self.get_verse(book_id, chapter, verse, t["code"]))
            for t in translations
        ]

    def get_verse_by_id(self, verse_id: int) -> Verse | None:
        row = self.conn.execute(
            """
            SELECT v.id, v.chapter, v.verse, v.text, b.name AS book_name, b.id AS book_id
            FROM verses v
            JOIN books b ON v.book_id = b.id
            WHERE v.id = ?
            """,
            (verse_id,),
        ).fetchone()
        return Verse.from_row(row) if row else None

    def get_chapter(self, book_id: int, chapter: int, translation_code: str) -> list[Verse]:
        rows = self.conn.execute(
            """
            SELECT v.id, v.chapter, v.verse, v.text, b.name AS book_name, b.id AS book_id
            FROM verses v
            JOIN books b ON v.book_id = b.id
            JOIN translations t ON v.translation_id = t.id
            WHERE v.book_id = ? AND v.chapter = ? AND t.code = ?
            ORDER BY v.verse
            """,
            (book_id, chapter, translation_code),
        ).fetchall()
        return [Verse.from_row(r) for r in rows]

    def search(
        self,
        query: str,
        translation_code: str,
        testament: str | None = None,
        category: str | None = None,
        book_id: int | None = None,
        limit: int = 100,
    ) -> list[Verse]:
        sql = """
            SELECT v.id, v.chapter, v.verse, v.text, b.name AS book_name, b.id AS book_id,
                   bm25(verses_fts) AS rank
            FROM verses_fts
            JOIN verses v ON verses_fts.rowid = v.id
            JOIN books b ON v.book_id = b.id
            JOIN translations t ON v.translation_id = t.id
            WHERE verses_fts MATCH ? AND t.code = ?
        """
        params: list = [query, translation_code]
        if testament:
            sql += " AND b.testament = ?"
            params.append(testament)
        if category:
            sql += " AND b.category = ?"
            params.append(category)
        if book_id:
            sql += " AND b.id = ?"
            params.append(book_id)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [Verse.from_row(r) for r in rows]

    def random_verse_id(self, translation_code: str, rng: random.Random | None = None) -> int | None:
        """A verse id drawn from `translation_code`.

        Pass a seeded `rng` for a repeatable draw - that is how the
        verse-of-the-day picks the same verse for everyone on a given date
        without storing a schedule.
        """
        rng = rng or random
        row = self.conn.execute(
            "SELECT MIN(v.id) AS lo, MAX(v.id) AS hi FROM verses v "
            "JOIN translations t ON v.translation_id = t.id WHERE t.code = ?",
            (translation_code,),
        ).fetchone()
        if not row or row["lo"] is None:
            return None
        lo, hi = row["lo"], row["hi"]
        while True:
            candidate = rng.randint(lo, hi)
            exists = self.conn.execute("SELECT 1 FROM verses WHERE id = ?", (candidate,)).fetchone()
            if exists:
                return candidate

    def verse_of_day_id(self, translation_code: str, day: str) -> int | None:
        """The verse for an ISO date - stable for the whole day, different
        the next."""
        return self.random_verse_id(translation_code, random.Random(f"{translation_code}:{day}"))

    # ------------------------------------------------------------------
    # Cross-references (translation-independent; see schema.sql)
    # ------------------------------------------------------------------

    def get_cross_references(
        self, book_id: int, chapter: int, verse: int, translation_code: str, limit: int = 15
    ) -> list[sqlite3.Row]:
        """Rows carry both the resolved Verse columns and `votes`, so callers
        get the preview text and the relevance ranking in one query."""
        return self.conn.execute(
            """
            SELECT v.id, v.chapter, v.verse, v.text, b.name AS book_name, b.id AS book_id, cr.votes AS votes
            FROM cross_references cr
            JOIN verses v ON v.book_id = cr.to_book_id AND v.chapter = cr.to_chapter AND v.verse = cr.to_verse
            JOIN books b ON v.book_id = b.id
            JOIN translations t ON v.translation_id = t.id
            WHERE cr.from_book_id = ? AND cr.from_chapter = ? AND cr.from_verse = ? AND t.code = ?
            ORDER BY cr.votes DESC
            LIMIT ?
            """,
            (book_id, chapter, verse, translation_code, limit),
        ).fetchall()

    # ------------------------------------------------------------------
    # Strong's concordance / interlinear (KJV-only; see schema.sql)
    # ------------------------------------------------------------------

    def get_strongs_for_verse(self, book_id: int, chapter: int, verse: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT vs.word_index, vs.word, s.code, s.transliteration, s.definition, s.language
            FROM verse_strongs vs
            JOIN strongs s ON vs.strongs_code = s.code
            JOIN verses v ON vs.verse_id = v.id
            JOIN translations t ON v.translation_id = t.id
            WHERE v.book_id = ? AND v.chapter = ? AND v.verse = ? AND t.code = 'KJV'
            ORDER BY vs.word_index
            """,
            (book_id, chapter, verse),
        ).fetchall()

    def search_strongs(self, query: str, limit: int = 50) -> list[sqlite3.Row]:
        """Bible dictionary lookup: Strong's entries whose code, definition,
        or transliteration match. Hebrew/Greek-word-scoped - not a plain-
        English dictionary of names and customs."""
        needle = f"%{query.strip()}%"
        return self.conn.execute(
            """
            SELECT code, language, transliteration, definition, pronunciation
            FROM strongs
            WHERE code LIKE ? OR definition LIKE ? OR transliteration LIKE ?
            ORDER BY code
            LIMIT ?
            """,
            (needle, needle, needle, limit),
        ).fetchall()

    # ------------------------------------------------------------------
    # Commentary (translation-independent; see schema.sql)
    # ------------------------------------------------------------------

    def get_commentary(self, book_id: int, chapter: int, verse: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT author, text, source_url FROM commentaries
            WHERE book_id = ? AND chapter = ? AND verse_start <= ? AND verse_end >= ?
            """,
            (book_id, chapter, verse, verse),
        ).fetchall()

    def study_markers_for_chapter(self, book_id: int, chapter: int) -> set[int]:
        """Verses with a cross-reference or commentary entry - the footnote
        marker in the reader, so ``s`` isn't a guess. Both tables are
        translation-independent, keyed like ``bookmarks`` by
        (book_id, chapter, verse), so no translation filter is needed."""
        verses: set[int] = set()
        for row in self.conn.execute(
            "SELECT DISTINCT from_verse FROM cross_references WHERE from_book_id = ? AND from_chapter = ?",
            (book_id, chapter),
        ):
            verses.add(row["from_verse"])
        for row in self.conn.execute(
            "SELECT verse_start, verse_end FROM commentaries WHERE book_id = ? AND chapter = ?",
            (book_id, chapter),
        ):
            verses.update(range(row["verse_start"], row["verse_end"] + 1))
        return verses

    # ------------------------------------------------------------------
    # Bookmarks
    # ------------------------------------------------------------------

    def add_bookmark(self, book_id: int, chapter: int, verse: int, label: str | None = None) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO bookmarks (book_id, chapter, verse, label) VALUES (?, ?, ?, ?)",
            (book_id, chapter, verse, label),
        )
        self.conn.commit()

    def remove_bookmark(self, book_id: int, chapter: int, verse: int) -> None:
        self.conn.execute(
            "DELETE FROM bookmarks WHERE book_id = ? AND chapter = ? AND verse = ?",
            (book_id, chapter, verse),
        )
        self.conn.commit()

    def is_bookmarked(self, book_id: int, chapter: int, verse: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM bookmarks WHERE book_id = ? AND chapter = ? AND verse = ?",
            (book_id, chapter, verse),
        ).fetchone()
        return row is not None

    def bookmarks_for_chapter(self, book_id: int, chapter: int) -> set[int]:
        rows = self.conn.execute(
            "SELECT verse FROM bookmarks WHERE book_id = ? AND chapter = ?", (book_id, chapter)
        ).fetchall()
        return {r["verse"] for r in rows}

    def set_bookmark_label(self, book_id: int, chapter: int, verse: int, label: str | None) -> None:
        """Name a bookmark, creating it if the verse isn't bookmarked yet -
        labelling a verse is a clear enough statement that you want to keep
        it that making you press `b` first would be a nuisance."""
        self.add_bookmark(book_id, chapter, verse)
        self.conn.execute(
            "UPDATE bookmarks SET label = ? WHERE book_id = ? AND chapter = ? AND verse = ?",
            (label or None, book_id, chapter, verse),
        )
        self.conn.commit()

    def get_bookmark_label(self, book_id: int, chapter: int, verse: int) -> str:
        row = self.conn.execute(
            "SELECT label FROM bookmarks WHERE book_id = ? AND chapter = ? AND verse = ?",
            (book_id, chapter, verse),
        ).fetchone()
        return (row["label"] or "") if row else ""

    def list_bookmarks(self, order: str = ORDER_RECENT) -> list[sqlite3.Row]:
        """Newest first by default; canonical order for reading through them.

        Canonical sorts on book_num rather than book_id so it still reads
        Genesis-to-Revelation if book ids are ever assigned some other way.
        """
        if order == ORDER_CANONICAL:
            clause = "b.book_num, bm.chapter, bm.verse"
        elif order == ORDER_FOLDER:
            # Unfiled bookmarks (folder_name NULL) sort last, not first.
            clause = "(f.name IS NULL), f.name, b.book_num, bm.chapter, bm.verse"
        else:
            clause = "bm.created_at DESC, bm.id DESC"
        return self.conn.execute(
            f"""
            SELECT bm.id, bm.book_id, b.name AS book_name, bm.chapter, bm.verse,
                   bm.label, bm.created_at, bm.folder_id, f.name AS folder_name
            FROM bookmarks bm
            JOIN books b ON bm.book_id = b.id
            LEFT JOIN bookmark_folders f ON bm.folder_id = f.id
            ORDER BY {clause}
            """
        ).fetchall()

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def add_note(self, book_id: int, chapter: int, verse: int, body: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO notes (book_id, chapter, verse, body) VALUES (?, ?, ?, ?)",
            (book_id, chapter, verse, body),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_notes(self, book_id: int, chapter: int, verse: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM notes WHERE book_id = ? AND chapter = ? AND verse = ? ORDER BY created_at",
            (book_id, chapter, verse),
        ).fetchall()

    def update_note(self, note_id: int, body: str) -> None:
        self.conn.execute(
            "UPDATE notes SET body = ?, updated_at = datetime('now') WHERE id = ?", (body, note_id)
        )
        self.conn.commit()

    def delete_note(self, note_id: int) -> None:
        self.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self.conn.commit()

    def notes_for_chapter(self, book_id: int, chapter: int) -> set[int]:
        rows = self.conn.execute(
            "SELECT DISTINCT verse FROM notes WHERE book_id = ? AND chapter = ?", (book_id, chapter)
        ).fetchall()
        return {r["verse"] for r in rows}

    # ------------------------------------------------------------------
    # Highlights
    # ------------------------------------------------------------------

    def set_highlight(self, book_id: int, chapter: int, verse: int, color: str = "yellow") -> None:
        self.conn.execute(
            """
            INSERT INTO highlights (book_id, chapter, verse, color) VALUES (?, ?, ?, ?)
            ON CONFLICT(book_id, chapter, verse) DO UPDATE SET color = excluded.color
            """,
            (book_id, chapter, verse, color),
        )
        self.conn.commit()

    def remove_highlight(self, book_id: int, chapter: int, verse: int) -> None:
        self.conn.execute(
            "DELETE FROM highlights WHERE book_id = ? AND chapter = ? AND verse = ?",
            (book_id, chapter, verse),
        )
        self.conn.commit()

    def highlights_for_chapter(self, book_id: int, chapter: int) -> dict[int, str]:
        rows = self.conn.execute(
            "SELECT verse, color FROM highlights WHERE book_id = ? AND chapter = ?", (book_id, chapter)
        ).fetchall()
        return {r["verse"]: r["color"] for r in rows}

    # ------------------------------------------------------------------
    # Bookmark folders
    # ------------------------------------------------------------------

    def create_folder(self, name: str) -> int:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO bookmark_folders (name) VALUES (?)", (name,)
        )
        self.conn.commit()
        if cur.lastrowid and cur.rowcount:
            return cur.lastrowid
        return self.conn.execute(
            "SELECT id FROM bookmark_folders WHERE name = ?", (name,)
        ).fetchone()["id"]

    def list_folders(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM bookmark_folders ORDER BY name").fetchall()

    def rename_folder(self, folder_id: int, name: str) -> None:
        self.conn.execute("UPDATE bookmark_folders SET name = ? WHERE id = ?", (name, folder_id))
        self.conn.commit()

    def delete_folder(self, folder_id: int) -> None:
        # Bookmarks in the folder become unfiled, not deleted.
        self.conn.execute("UPDATE bookmarks SET folder_id = NULL WHERE folder_id = ?", (folder_id,))
        self.conn.execute("DELETE FROM bookmark_folders WHERE id = ?", (folder_id,))
        self.conn.commit()

    def set_bookmark_folder(self, book_id: int, chapter: int, verse: int, folder_id: int | None) -> None:
        self.add_bookmark(book_id, chapter, verse)
        self.conn.execute(
            "UPDATE bookmarks SET folder_id = ? WHERE book_id = ? AND chapter = ? AND verse = ?",
            (folder_id, book_id, chapter, verse),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def _get_or_create_tag(self, name: str) -> int:
        name = name.strip().lower()
        cur = self.conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        self.conn.commit()
        if cur.lastrowid and cur.rowcount:
            return cur.lastrowid
        return self.conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()["id"]

    def list_tags(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM tags ORDER BY name").fetchall()

    def tag_verse(self, book_id: int, chapter: int, verse: int, name: str) -> None:
        tag_id = self._get_or_create_tag(name)
        self.conn.execute(
            "INSERT OR IGNORE INTO verse_tags (book_id, chapter, verse, tag_id) VALUES (?, ?, ?, ?)",
            (book_id, chapter, verse, tag_id),
        )
        self.conn.commit()

    def untag_verse(self, book_id: int, chapter: int, verse: int, name: str) -> None:
        self.conn.execute(
            """
            DELETE FROM verse_tags WHERE book_id = ? AND chapter = ? AND verse = ?
            AND tag_id = (SELECT id FROM tags WHERE name = ?)
            """,
            (book_id, chapter, verse, name.strip().lower()),
        )
        self.conn.commit()

    def tags_for_verse(self, book_id: int, chapter: int, verse: int) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT t.name FROM verse_tags vt JOIN tags t ON vt.tag_id = t.id
            WHERE vt.book_id = ? AND vt.chapter = ? AND vt.verse = ? ORDER BY t.name
            """,
            (book_id, chapter, verse),
        ).fetchall()
        return [r["name"] for r in rows]

    def tag_note(self, note_id: int, name: str) -> None:
        tag_id = self._get_or_create_tag(name)
        self.conn.execute(
            "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)", (note_id, tag_id)
        )
        self.conn.commit()

    def tags_for_note(self, note_id: int) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT t.name FROM note_tags nt JOIN tags t ON nt.tag_id = t.id
            WHERE nt.note_id = ? ORDER BY t.name
            """,
            (note_id,),
        ).fetchall()
        return [r["name"] for r in rows]

    def verses_tagged(self, name: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT vt.book_id, vt.chapter, vt.verse FROM verse_tags vt
            JOIN tags t ON vt.tag_id = t.id WHERE t.name = ?
            ORDER BY vt.book_id, vt.chapter, vt.verse
            """,
            (name.strip().lower(),),
        ).fetchall()

    # ------------------------------------------------------------------
    # Favourites
    # ------------------------------------------------------------------

    def toggle_favourite(self, book_id: int, chapter: int, verse: int) -> bool:
        if self.is_favourite(book_id, chapter, verse):
            self.conn.execute(
                "DELETE FROM favourites WHERE book_id = ? AND chapter = ? AND verse = ?",
                (book_id, chapter, verse),
            )
            self.conn.commit()
            return False
        self.conn.execute(
            "INSERT OR IGNORE INTO favourites (book_id, chapter, verse) VALUES (?, ?, ?)",
            (book_id, chapter, verse),
        )
        self.conn.commit()
        return True

    def is_favourite(self, book_id: int, chapter: int, verse: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM favourites WHERE book_id = ? AND chapter = ? AND verse = ?",
            (book_id, chapter, verse),
        ).fetchone()
        return row is not None

    def list_favourites(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT f.book_id, b.name AS book_name, f.chapter, f.verse, f.created_at
            FROM favourites f JOIN books b ON f.book_id = b.id
            ORDER BY f.created_at DESC, f.rowid DESC
            """
        ).fetchall()

    # ------------------------------------------------------------------
    # Reading lists
    # ------------------------------------------------------------------

    def create_reading_list(self, name: str) -> int:
        cur = self.conn.execute("INSERT INTO reading_lists (name) VALUES (?)", (name,))
        self.conn.commit()
        return cur.lastrowid

    def list_reading_lists(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM reading_lists ORDER BY name").fetchall()

    def rename_reading_list(self, list_id: int, name: str) -> None:
        self.conn.execute("UPDATE reading_lists SET name = ? WHERE id = ?", (name, list_id))
        self.conn.commit()

    def delete_reading_list(self, list_id: int) -> None:
        self.conn.execute("DELETE FROM reading_list_items WHERE list_id = ?", (list_id,))
        self.conn.execute("DELETE FROM reading_lists WHERE id = ?", (list_id,))
        self.conn.commit()

    def add_to_reading_list(self, list_id: int, book_id: int, chapter: int, verse: int) -> int:
        cur = self.conn.execute(
            "INSERT INTO reading_list_items (list_id, book_id, chapter, verse) VALUES (?, ?, ?, ?)",
            (list_id, book_id, chapter, verse),
        )
        self.conn.commit()
        return cur.lastrowid

    def remove_from_reading_list(self, item_id: int) -> None:
        self.conn.execute("DELETE FROM reading_list_items WHERE id = ?", (item_id,))
        self.conn.commit()

    def reading_list_items(self, list_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT i.id, i.book_id, b.name AS book_name, i.chapter, i.verse, i.added_at
            FROM reading_list_items i JOIN books b ON i.book_id = b.id
            WHERE i.list_id = ? ORDER BY i.added_at
            """,
            (list_id,),
        ).fetchall()

    # ------------------------------------------------------------------
    # Last position / settings
    # ------------------------------------------------------------------

    def get_setting(self, key: str, default=None):
        """Read a JSON-encoded value out of the settings table."""
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (TypeError, ValueError):
            return default

    def set_setting(self, key: str, value) -> None:
        self.conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, json.dumps(value)),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Search vocabulary (typo tolerance)
    # ------------------------------------------------------------------

    def vocabulary(self, min_occurrences: int = 2) -> dict[str, int]:
        """Every distinct token in the search index, mapped to its frequency.

        Built from FTS5's own `fts5vocab` view, so the terms are exactly what
        the index holds - stemmed and lower-cased. Rare tokens are skipped:
        suggesting a hapax legomenon as a correction is noise. The counts let
        a spelling correction prefer a common word over an obscure one.
        Cached because the list is ~10k entries and never changes at runtime.
        """
        if self._vocabulary is not None:
            return self._vocabulary
        try:
            self.conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS temp.verses_vocab "
                "USING fts5vocab(main, verses_fts, 'row')"
            )
            rows = self.conn.execute(
                "SELECT term, cnt FROM temp.verses_vocab WHERE cnt >= ?", (min_occurrences,)
            ).fetchall()
            self._vocabulary = {r["term"]: r["cnt"] for r in rows}
        except sqlite3.Error:
            # An older SQLite without fts5vocab just means no suggestions.
            self._vocabulary = {}
        return self._vocabulary

    #: Per-book reading positions, so returning to a book returns you to
    #: where you stopped in it rather than to chapter 1.
    _BOOK_POSITIONS = "book_positions"

    def book_position(self, book_id: int) -> tuple[int, int] | None:
        """The (chapter, verse) last read in `book_id`, if any."""
        stored = self.get_setting(self._BOOK_POSITIONS, {})
        entry = stored.get(str(book_id)) if isinstance(stored, dict) else None
        if isinstance(entry, list) and len(entry) == 2:
            return int(entry[0]), int(entry[1])
        return None

    def remember_book_position(self, book_id: int, chapter: int, verse: int = 0) -> None:
        stored = self.get_setting(self._BOOK_POSITIONS, {})
        if not isinstance(stored, dict):
            stored = {}
        stored[str(book_id)] = [chapter, verse]
        self.set_setting(self._BOOK_POSITIONS, stored)

    def get_last_position(self) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM last_position WHERE id = 1").fetchone()

    def set_last_position(self, translation_code: str, book_id: int, chapter: int) -> None:
        self.conn.execute(
            """
            INSERT INTO last_position (id, translation_code, book_id, chapter) VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET translation_code = excluded.translation_code,
                                           book_id = excluded.book_id, chapter = excluded.chapter
            """,
            (translation_code, book_id, chapter),
        )
        self.conn.commit()
