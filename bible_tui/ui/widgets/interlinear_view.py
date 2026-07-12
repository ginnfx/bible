from __future__ import annotations

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static

from ...models.study import InterlinearWord


class InterlinearWordCell(Static):
    """One word stacked as English / transliteration / Strong's code, in a
    fixed-width cell so alignment holds regardless of word-length
    differences - terminal apps are naturally suited to this compared to a
    browser needing custom CSS grid work to get the same effect."""

    DEFAULT_CSS = """
    InterlinearWordCell {
        width: auto;
        min-width: 12;
        padding: 0 2 1 0;
    }
    """

    def __init__(self, word: InterlinearWord):
        lang_color = "yellow" if word.language == "Hebrew" else "cyan"
        content = (
            f"[bold]{word.word}[/]\n"
            f"[italic]{word.transliteration}[/]\n"
            f"[{lang_color}]{word.strongs_code}[/]"
        )
        super().__init__(content)
        self.word = word


class InterlinearView(VerticalScroll):
    """Row of word cells for a verse's interlinear breakdown, plus the full
    definition of whichever word is currently focused."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._words: list[InterlinearWord] = []

    def load_words(self, words: list[InterlinearWord]) -> None:
        self._words = words
        self.remove_children()
        if not words:
            self.mount(Static("[dim]No Strong's data available for this verse.[/]"))
            return
        row = Horizontal(*[InterlinearWordCell(w) for w in words])
        self.mount(row)
        self.mount(Static(""))
        for w in words:
            self.mount(Static(f"[bold]{w.strongs_code}[/] ({w.language}) - {w.definition}"))
