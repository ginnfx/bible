"""Translation picker overlay, opened with ``v``.

Mirrors christ-cli's popup: every available translation with its full name,
the current one ticked, Enter to apply and Esc (or ``v`` again) to back out.
"""

from __future__ import annotations

import sqlite3

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option


class TranslationScreen(ModalScreen[str | None]):
    """Returns the chosen translation code, or None when dismissed."""

    DEFAULT_CSS = """
    TranslationScreen {
        align: center middle;
        background: $background 60%;
    }
    TranslationScreen OptionList {
        width: 56;
        height: auto;
        max-height: 80%;
        border: round $border;
        background: $surface;
        padding: 1 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("v", "close", "Close", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, translations: list[sqlite3.Row], current: str) -> None:
        super().__init__()
        self._translations = translations
        self._current = current

    def compose(self) -> ComposeResult:
        option_list = OptionList(
            *[self._option(t) for t in self._translations], id="translation-list"
        )
        option_list.border_title = "Select Translation"
        option_list.border_subtitle = "Enter applies · Esc closes"
        yield option_list

    def _option(self, row: sqlite3.Row) -> Option:
        code = row["code"]
        year = row["year"] if "year" in row.keys() and row["year"] else None
        suffix = f" ({year})" if year else ""
        tick = "  [b $bible-search-match]✓[/]" if code == self._current else ""
        return Option(f"[b]{code:<6}[/] {row['name']}{suffix}{tick}", id=code)

    def on_mount(self) -> None:
        option_list = self.query_one("#translation-list", OptionList)
        codes = [t["code"] for t in self._translations]
        if self._current in codes:
            option_list.highlighted = codes.index(self._current)
        option_list.focus()

    def action_cursor_down(self) -> None:
        self.query_one("#translation-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#translation-list", OptionList).action_cursor_up()

    def action_close(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id))
