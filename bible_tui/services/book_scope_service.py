"""Testament/category scopes for browsing and search alike.

One canonical list, cycled by the Books panel's `tab` (see
``ui/screens/reader.py``) and by search's own scope cycling (see
``ui/screens/search.py``) - so a new category never has to be taught to two
places, and the two "narrow what I'm looking at" features never drift out
of sync with each other or with the real category set in
``models/book.py``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class BookScope:
    label: str
    testament: str | None = None  # 'OT' or 'NT'
    category: str | None = None

    def matches(self, book: sqlite3.Row) -> bool:
        if self.testament is not None and book["testament"] != self.testament:
            return False
        if self.category is not None and book["category"] != self.category:
            return False
        return True


#: Whole Bible, both testaments, then every category in canonical
#: (OT-to-NT, front-to-back) order - 12 scopes total, one per real category
#: plus the two testaments plus "no filter."
BOOK_SCOPES: tuple[BookScope, ...] = (
    BookScope("Whole Bible"),
    BookScope("Old Testament", testament="OT"),
    BookScope("New Testament", testament="NT"),
    BookScope("Law", category="Law"),
    BookScope("History", category="History"),
    BookScope("Poetry", category="Poetry"),
    BookScope("Major Prophets", category="Major Prophets"),
    BookScope("Minor Prophets", category="Minor Prophets"),
    BookScope("Gospels", category="Gospels"),
    BookScope("Acts", category="Acts"),
    BookScope("Epistles", category="Epistles"),
    BookScope("Apocalyptic", category="Apocalyptic"),
)


def filter_books(books: list[sqlite3.Row], scope: BookScope) -> list[sqlite3.Row]:
    return [book for book in books if scope.matches(book)]


def breadcrumb(book: sqlite3.Row) -> str:
    """Compact ``OT · Major Prophets`` label for the scripture panel's
    border title - terse enough to fit alongside the book/chapter that's
    already there."""
    return f"{book['testament']} · {book['category']}"
