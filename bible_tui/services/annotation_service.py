from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..data.repository import ORDER_RECENT, BibleRepository


@dataclass
class AnnotationService:
    repo: BibleRepository

    def toggle_bookmark(self, book_id: int, chapter: int, verse: int) -> bool:
        """Returns the new bookmarked state."""
        if self.repo.is_bookmarked(book_id, chapter, verse):
            self.repo.remove_bookmark(book_id, chapter, verse)
            return False
        self.repo.add_bookmark(book_id, chapter, verse)
        return True

    def is_bookmarked(self, book_id: int, chapter: int, verse: int) -> bool:
        return self.repo.is_bookmarked(book_id, chapter, verse)

    def bookmarks_for_chapter(self, book_id: int, chapter: int) -> set[int]:
        return self.repo.bookmarks_for_chapter(book_id, chapter)

    def list_bookmarks(self, order: str = ORDER_RECENT) -> list[sqlite3.Row]:
        return self.repo.list_bookmarks(order)

    def label_bookmark(self, book_id: int, chapter: int, verse: int, label: str | None) -> None:
        self.repo.set_bookmark_label(book_id, chapter, verse, label)

    def bookmark_label(self, book_id: int, chapter: int, verse: int) -> str:
        return self.repo.get_bookmark_label(book_id, chapter, verse)

    def remove_bookmark(self, book_id: int, chapter: int, verse: int) -> None:
        self.repo.remove_bookmark(book_id, chapter, verse)

    def find_bookmarks(self, needle: str, order: str = ORDER_RECENT) -> list[sqlite3.Row]:
        """Filter by label or reference, case-insensitively.

        Done in Python rather than SQL because the thing people type is
        usually a reference ("john 3") which spans two columns, and the list
        is small enough that a scan is instant.
        """
        needle = needle.strip().lower()
        rows = self.list_bookmarks(order)
        if not needle:
            return rows
        return [
            row
            for row in rows
            if needle in (row["label"] or "").lower()
            or needle in f"{row['book_name']} {row['chapter']}:{row['verse']}".lower()
        ]

    def add_note(self, book_id: int, chapter: int, verse: int, body: str) -> int:
        return self.repo.add_note(book_id, chapter, verse, body)

    def get_notes(self, book_id: int, chapter: int, verse: int) -> list[sqlite3.Row]:
        return self.repo.get_notes(book_id, chapter, verse)

    def update_note(self, note_id: int, body: str) -> None:
        self.repo.update_note(note_id, body)

    def delete_note(self, note_id: int) -> None:
        self.repo.delete_note(note_id)

    def notes_for_chapter(self, book_id: int, chapter: int) -> set[int]:
        return self.repo.notes_for_chapter(book_id, chapter)

    def tag_note(self, note_id: int, name: str) -> None:
        self.repo.tag_note(note_id, name)

    def tags_for_note(self, note_id: int) -> list[str]:
        return self.repo.tags_for_note(note_id)

    def cycle_highlight(self, book_id: int, chapter: int, verse: int) -> str | None:
        """Cycles through colors and off; returns the new color or None if cleared."""
        colors = ["yellow", "green", "blue", "pink"]
        current = self.repo.highlights_for_chapter(book_id, chapter).get(verse)
        if current is None:
            self.repo.set_highlight(book_id, chapter, verse, colors[0])
            return colors[0]
        idx = colors.index(current) if current in colors else -1
        if idx + 1 < len(colors):
            self.repo.set_highlight(book_id, chapter, verse, colors[idx + 1])
            return colors[idx + 1]
        self.repo.remove_highlight(book_id, chapter, verse)
        return None

    def highlights_for_chapter(self, book_id: int, chapter: int) -> dict[int, str]:
        return self.repo.highlights_for_chapter(book_id, chapter)

    # ------------------------------------------------------------------
    # Bookmark folders
    # ------------------------------------------------------------------

    def create_folder(self, name: str) -> int:
        return self.repo.create_folder(name)

    def list_folders(self) -> list[sqlite3.Row]:
        return self.repo.list_folders()

    def rename_folder(self, folder_id: int, name: str) -> None:
        self.repo.rename_folder(folder_id, name)

    def delete_folder(self, folder_id: int) -> None:
        self.repo.delete_folder(folder_id)

    def set_bookmark_folder(self, book_id: int, chapter: int, verse: int, folder_id: int | None) -> None:
        self.repo.set_bookmark_folder(book_id, chapter, verse, folder_id)

    # ------------------------------------------------------------------
    # Verse tags
    # ------------------------------------------------------------------

    def list_tags(self) -> list[sqlite3.Row]:
        return self.repo.list_tags()

    def tag_verse(self, book_id: int, chapter: int, verse: int, name: str) -> None:
        self.repo.tag_verse(book_id, chapter, verse, name)

    def untag_verse(self, book_id: int, chapter: int, verse: int, name: str) -> None:
        self.repo.untag_verse(book_id, chapter, verse, name)

    def tags_for_verse(self, book_id: int, chapter: int, verse: int) -> list[str]:
        return self.repo.tags_for_verse(book_id, chapter, verse)

    def verses_tagged(self, name: str) -> list[sqlite3.Row]:
        return self.repo.verses_tagged(name)

    # ------------------------------------------------------------------
    # Favourites
    # ------------------------------------------------------------------

    def toggle_favourite(self, book_id: int, chapter: int, verse: int) -> bool:
        return self.repo.toggle_favourite(book_id, chapter, verse)

    def is_favourite(self, book_id: int, chapter: int, verse: int) -> bool:
        return self.repo.is_favourite(book_id, chapter, verse)

    def list_favourites(self) -> list[sqlite3.Row]:
        return self.repo.list_favourites()
