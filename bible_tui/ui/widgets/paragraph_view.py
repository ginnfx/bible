"""Paragraph reading view: the chapter as flowing prose.

Verse numbers become small markers inside the text rather than a left
gutter, which is what makes a chapter read like a page instead of like a
database dump. Toggled against ``VerseView`` with ``p``.
"""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static

from ...models.verse import Verse
from ..theme import rich_color


class ParagraphView(VerticalScroll):
    """Scrollable prose rendering of the current chapter.

    Single column by default; ``scripture_columns=2`` splits the verses
    roughly in half across two side-by-side statics instead - a page-like
    layout, not a second independently-scrollable pane (`VerseView`'s
    cursor-based verse-per-line mode stays single-column; splitting a
    ``ListView``'s single cursor across two panes is the same class of
    problem as the deferred multi-pane reader, out of scope here).
    """

    DEFAULT_CSS = """
    ParagraphView {
        padding: 1 2;
        scrollbar-size-vertical: 1;
    }
    ParagraphView > Static {
        width: 1fr;
    }
    ParagraphView #paragraph-columns {
        height: auto;
    }
    ParagraphView .paragraph-column {
        width: 1fr;
        padding-right: 2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._verses: list[Verse] = []
        self._highlights: dict[int, str] = {}
        self._body = Static("", id="paragraph-body")
        self._col_a = Static("", id="paragraph-col-a", classes="paragraph-column")
        self._col_b = Static("", id="paragraph-col-b", classes="paragraph-column")

    def compose(self):
        yield self._body
        with Horizontal(id="paragraph-columns"):
            yield self._col_a
            yield self._col_b

    def load_chapter(
        self, verses: list[Verse], highlighted: dict[int, str], columns: int = 1
    ) -> None:
        self._verses = verses
        self._highlights = highlighted
        columns_row = self.query_one("#paragraph-columns")

        if columns == 2 and verses:
            self._body.display = False
            columns_row.display = True
            midpoint = (len(verses) + 1) // 2
            self._col_a.update(self._build(verses[:midpoint]))
            self._col_b.update(self._build(verses[midpoint:]))
        else:
            columns_row.display = False
            self._body.display = True
            self._body.update(self._build(verses))
        self.scroll_home(animate=False)

    def _build(self, verses: list[Verse]) -> Text:
        from .verse_view import HIGHLIGHT_STYLES

        number_style = rich_color(self.app, "bible-verse-number", "dim")
        body = Text(no_wrap=False)
        for i, verse in enumerate(verses):
            if i:
                body.append("  ")
            body.append(str(verse.verse), style=number_style)
            body.append(" ")
            color = self._highlights.get(verse.verse)
            body.append(verse.text, style=HIGHLIGHT_STYLES.get(color, "") if color else "")
        return body

    @property
    def verses(self) -> list[Verse]:
        return self._verses
