from __future__ import annotations

import textwrap

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import ListItem, ListView, Static

from ...config import SPACING_LEVELS, WRAP_HARD, WRAP_NONE
from ...models.verse import Verse

#: Column a "hard" line wrap pre-wraps to, chosen to read comfortably in a
#: reasonably narrow terminal without the reader having to resize.
_HARD_WRAP_COLUMN = 70

#: Rich styles for the highlight colours cycled with ``m``. Shared with the
#: paragraph view so a highlight looks the same in either reading mode.
HIGHLIGHT_STYLES = {
    "yellow": "black on #f5e642",
    "green": "black on #8fe38f",
    "blue": "white on #6ea8fe",
    "pink": "black on #f7a8c4",
}


class VerseItem(ListItem):
    """One verse: a fixed-width number gutter beside wrapping verse text.

    Splitting the row in two is what gives long verses a hanging indent -
    a single label would wrap continuation lines back under the number.
    """

    def __init__(self, verse: Verse, body: Text) -> None:
        super().__init__()
        self.verse = verse
        self._body = body

    def compose(self) -> ComposeResult:
        yield Static(str(self.verse.verse), classes="verse-number")
        yield Static(self._body, classes="verse-text")


class VerseView(ListView):
    """Verse-per-line reading view for the current chapter.

    Each verse is a ``ListItem`` so up/down/home/end navigation and cursor
    highlighting come from Textual; bookmark/note markers and highlight
    colours are Rich markup in the body. A *visual range* (started with
    ``Y``) is drawn by toggling a CSS class on the items inside it rather
    than re-rendering the list, so extending a selection across Psalm 119
    stays instant.
    """

    DEFAULT_CSS = """
    VerseView > ListItem {
        height: auto;
        layout: horizontal;
        padding: 0 1;
    }
    VerseView > ListItem.in-range {
        background: $bible-cursor-bg;
    }
    VerseView .verse-number {
        width: 5;
        text-align: right;
        padding-right: 1;
        color: $bible-verse-number;
    }
    VerseView .verse-text {
        width: 1fr;
        text-align: left;
    }
    VerseView.wrap-none .verse-text {
        width: auto;
        overflow-x: auto;
    }
    VerseView.spacing-compact > ListItem { margin-bottom: 0; }
    VerseView.spacing-comfortable > ListItem { margin-bottom: 1; }
    VerseView.spacing-spacious > ListItem { margin-bottom: 2; }
    VerseView.low-vision-cursor > ListItem.-highlight {
        border-left: thick $accent;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._verses: list[Verse] = []
        self._anchor: int | None = None

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def load_chapter(
        self,
        verses: list[Verse],
        bookmarked: set[int],
        highlighted: dict[int, str],
        noted: set[int],
        studied: set[int] = frozenset(),
        line_wrap: str = "soft",
        verse_spacing: str = "comfortable",
        low_vision: bool = False,
    ) -> None:
        self._verses = verses
        self._anchor = None
        self.set_class(line_wrap == WRAP_NONE, "wrap-none")
        for level in SPACING_LEVELS:
            self.set_class(verse_spacing == level, f"spacing-{level}")
        self.set_class(low_vision, "low-vision-cursor")
        self.clear()
        self.extend(
            VerseItem(v, self._render_body(v, bookmarked, highlighted, noted, studied, line_wrap))
            for v in verses
        )
        if verses:
            self.index = 0

    @staticmethod
    def _render_body(
        v: Verse,
        bookmarked: set[int],
        highlighted: dict[int, str],
        noted: set[int],
        studied: set[int] = frozenset(),
        line_wrap: str = "soft",
    ) -> Text:
        # Built as a rich Text rather than Textual markup: a verse wraps, and
        # Textual's markup opens a gap at every styled span when it does.
        text = v.text
        if line_wrap == WRAP_HARD:
            text = "\n".join(textwrap.wrap(text, _HARD_WRAP_COLUMN)) or text
        body = Text(no_wrap=(line_wrap == WRAP_NONE))
        if v.verse in bookmarked:
            body.append("★ ")
        if v.verse in noted:
            body.append("\U0001f4dd ")
        if v.verse in studied:
            # Cross-references or commentary exist for this verse - 's'
            # opens them. Distinct from the bookmark/note glyphs above,
            # which mark the reader's own annotations rather than content
            # the app already has.
            body.append("† ")
        color = highlighted.get(v.verse)
        style = HIGHLIGHT_STYLES.get(color, HIGHLIGHT_STYLES["yellow"]) if color else ""
        body.append(text, style=style)
        return body

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    @property
    def verses(self) -> list[Verse]:
        return self._verses

    @property
    def selected_verse(self) -> Verse | None:
        if self.index is None or not self._verses:
            return None
        if 0 <= self.index < len(self._verses):
            return self._verses[self.index]
        return None

    def select_verse_number(self, number: int) -> None:
        """Move the cursor to a verse by *number*, not index - translations
        can have numbering gaps, so the two aren't interchangeable."""
        for i, v in enumerate(self._verses):
            if v.verse == number:
                self.index = i
                return

    # ------------------------------------------------------------------
    # Visual range (Y)
    # ------------------------------------------------------------------

    @property
    def has_range(self) -> bool:
        return self._anchor is not None

    def start_range(self) -> None:
        self._anchor = self.index or 0
        self.refresh_range()

    def clear_range(self) -> None:
        self._anchor = None
        for item in self.query(ListItem):
            item.remove_class("in-range")

    def range_bounds(self) -> tuple[int, int]:
        """Inclusive (start, end) indices of the current selection - just the
        cursor position when no range is active."""
        cursor = self.index or 0
        if self._anchor is None:
            return cursor, cursor
        return min(self._anchor, cursor), max(self._anchor, cursor)

    def selected_verses(self) -> list[Verse]:
        start, end = self.range_bounds()
        return self._verses[start : end + 1]

    def refresh_range(self) -> None:
        """Re-apply the range class after the cursor moves."""
        if self._anchor is None:
            return
        start, end = self.range_bounds()
        for i, item in enumerate(self.query(ListItem)):
            item.set_class(start <= i <= end, "in-range")

    def watch_index(self, old_index: int | None, new_index: int | None) -> None:
        super().watch_index(old_index, new_index)
        self.refresh_range()
