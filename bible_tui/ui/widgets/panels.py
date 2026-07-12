"""The Books and Chapters sidebars of the three-panel browser.

Both are thin ``OptionList`` wrappers: the list widget already gives us
keyboard navigation, mouse clicks, and scroll-to-highlight, so these only add
the panel chrome and the "moving the cursor arms a preview" message that the
reader debounces into a chapter load.
"""

from __future__ import annotations

import sqlite3

from textual.widgets import OptionList
from textual.widgets.option_list import Option


class BrowserPanel(OptionList):
    """Shared chrome: a rounded border whose colour tracks focus, matching
    christ-cli's active/inactive panel treatment."""

    DEFAULT_CSS = """
    BrowserPanel {
        height: 1fr;
        border: round $border-blurred;
        background: $surface;
        padding: 0 1;
        scrollbar-size-vertical: 1;
    }
    BrowserPanel:focus {
        border: round $border;
    }
    BrowserPanel > .option-list--option-highlighted {
        background: $bible-cursor-bg;
        color: $bible-cursor-fg;
        text-style: bold;
    }
    BrowserPanel:focus > .option-list--option-highlighted {
        background: $bible-cursor-bg;
        color: $bible-cursor-fg;
        text-style: bold;
    }
    """


class BookList(BrowserPanel):
    """The 66 books in canonical order, or a testament/category subset of
    them once `tab` narrows the scope (see ReaderScreen). Width is sized to
    the longest name so wide terminals give their space to scripture
    instead of to empty gutter."""

    def __init__(self, books: list[sqlite3.Row], **kwargs) -> None:
        super().__init__(**kwargs)
        self.border_title = "Books"
        self._book_ids: list[int] = []
        self.reload(books)

    def reload(self, books: list[sqlite3.Row], selected_book_id: int | None = None) -> None:
        """Rebuild for a (possibly filtered) book set. Keeps the cursor on
        `selected_book_id` if it's still present in the new set; otherwise
        lands on top of the new list without touching anything else -
        narrowing what's *listed* here is not itself navigation."""
        self.clear_options()
        self.add_options([Option(book["name"], id=str(book["id"])) for book in books])
        self._book_ids = [book["id"] for book in books]
        if selected_book_id is not None and selected_book_id in self._book_ids:
            self.highlighted = self._book_ids.index(selected_book_id)
        elif self._book_ids:
            self.highlighted = 0

    @property
    def selected_book_id(self) -> int | None:
        if self.highlighted is None:
            return None
        return self._book_ids[self.highlighted]

    def select_book_id(self, book_id: int) -> None:
        if book_id in self._book_ids:
            self.highlighted = self._book_ids.index(book_id)


class ChapterList(BrowserPanel):
    """Chapter numbers for whichever book the Books panel is sitting on."""

    DEFAULT_CSS = """
    ChapterList {
        width: 10;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.border_title = "Ch"
        self._count = 0

    def load_chapters(self, count: int, selected: int = 1) -> None:
        """Rebuild the list only when the count actually changes - a preview
        that stays inside the same book shouldn't churn the widget."""
        if count != self._count:
            self._count = count
            self.clear_options()
            self.add_options([Option(str(n), id=str(n)) for n in range(1, count + 1)])
        if 1 <= selected <= count:
            self.highlighted = selected - 1

    @property
    def selected_chapter(self) -> int | None:
        if self.highlighted is None:
            return None
        return self.highlighted + 1
