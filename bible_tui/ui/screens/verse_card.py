"""A single centred card for one verse or a short range.

What ``bible read John 3:16`` shows when stdout is a terminal. Piped output
skips this entirely and prints plain text, so the command stays usable in a
shell pipeline.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Static

from ...models.verse import Verse
from ..theme import PALETTES, THEME_VARIABLE_DEFAULTS, rich_color


class VerseCardApp(App):
    """One-shot viewer: renders the card, exits on q/esc/enter."""

    BINDINGS = [Binding("q,escape,enter", "quit", "Close")]

    CSS = """
    Screen {
        align: center middle;
        background: $background;
    }
    #card {
        width: 80%;
        max-width: 80;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    #card-reference {
        width: 1fr;
        color: $accent;
        text-style: bold;
    }
    #card-body {
        width: 1fr;
        margin-top: 1;
    }
    #card-badge {
        width: 1fr;
        color: $text-disabled;
        text-align: right;
        margin-top: 1;
    }
    #card-hint {
        dock: bottom;
        width: 1fr;
        height: 1;
        color: $text-disabled;
        text-align: center;
    }
    """

    def __init__(self, verses: list[Verse], translation_code: str, theme_name: str) -> None:
        super().__init__()
        self._verses = verses
        self._translation = translation_code
        for palette in PALETTES:
            self.register_theme(palette.theme)
        self.theme = theme_name

    def get_theme_variable_defaults(self) -> dict[str, str]:
        return THEME_VARIABLE_DEFAULTS

    def compose(self) -> ComposeResult:
        with Vertical(id="card"):
            yield Static(self._reference(), id="card-reference")
            yield Static(self._body(), id="card-body")
            yield Static(self._translation, id="card-badge")
        yield Static("Press q or Esc to exit", id="card-hint")

    def _reference(self) -> str:
        first, last = self._verses[0], self._verses[-1]
        if first is last:
            return first.reference
        return f"{first.book_name} {first.chapter}:{first.verse}-{last.verse}"

    def _body(self) -> Text:
        if len(self._verses) == 1:
            return Text(self._verses[0].text)

        number_style = rich_color(self, "bible-verse-number", "dim")
        body = Text()
        for i, verse in enumerate(self._verses):
            if i:
                body.append("\n")
            body.append(str(verse.verse), style=number_style)
            body.append(f" {verse.text}")
        return body
