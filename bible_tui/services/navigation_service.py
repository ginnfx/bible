from __future__ import annotations

from dataclasses import dataclass, field

from ..data.repository import BibleRepository
from ..models.verse import Verse


@dataclass
class NavigationService:
    repo: BibleRepository
    translation_code: str = "KJV"
    _history: list[tuple[int, int]] = field(default_factory=list)  # (book_id, chapter)
    _position: int = -1

    def go_to_chapter(self, book_id: int, chapter: int) -> list[Verse]:
        verses = self.repo.get_chapter(book_id, chapter, self.translation_code)
        if not verses:
            return []
        self._push_history(book_id, chapter)
        return verses

    def _push_history(self, book_id: int, chapter: int) -> None:
        # Drop forward history whenever a fresh jump happens.
        self._history = self._history[: self._position + 1]
        self._history.append((book_id, chapter))
        self._position = len(self._history) - 1

    def back(self) -> tuple[int, int] | None:
        if self._position <= 0:
            return None
        self._position -= 1
        return self._history[self._position]

    def forward(self) -> tuple[int, int] | None:
        if self._position >= len(self._history) - 1:
            return None
        self._position += 1
        return self._history[self._position]

    def current_position(self) -> tuple[int, int] | None:
        if self._position < 0:
            return None
        return self._history[self._position]

    def next_chapter(self, book_id: int, chapter: int) -> tuple[int, int] | None:
        total = self.repo.chapter_count(book_id)
        if chapter < total:
            return (book_id, chapter + 1)
        next_book = self.repo.conn.execute(
            "SELECT id FROM books WHERE book_num = (SELECT book_num + 1 FROM books WHERE id = ?)",
            (book_id,),
        ).fetchone()
        if not next_book:
            return None
        return (next_book["id"], 1)

    def prev_chapter(self, book_id: int, chapter: int) -> tuple[int, int] | None:
        if chapter > 1:
            return (book_id, chapter - 1)
        prev_book = self.repo.conn.execute(
            """
            SELECT id, chapter_count FROM books
            WHERE book_num = (SELECT book_num - 1 FROM books WHERE id = ?)
            """,
            (book_id,),
        ).fetchone()
        if not prev_book:
            return None
        return (prev_book["id"], prev_book["chapter_count"])
