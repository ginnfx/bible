"""Display settings - line wrap, verse spacing, low-vision mode, chapter
heading, and column count, gathered into one picker rather than five more
raw keybindings. Mirrors `TranslationScreen`'s OptionList popup; enter
cycles/toggles the highlighted setting in place, escape applies and closes.

Returns the edited `Config` (immutable - each toggle replaces it with
`dataclasses.replace`, never mutates the one passed in) so the reader can
decide what to persist and what to re-render.
"""

from __future__ import annotations

from dataclasses import replace

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ...config import SPACING_LEVELS, WRAP_MODES, Config

_ROWS = ("line_wrap", "verse_spacing", "low_vision", "show_chapter_heading", "scripture_columns")

_LABELS = {
    "line_wrap": "Line wrap",
    "verse_spacing": "Verse spacing",
    "low_vision": "Low-vision mode",
    "show_chapter_heading": "Chapter heading",
    "scripture_columns": "Columns",
}


def _cycle_value(config: Config, field: str) -> Config:
    if field == "line_wrap":
        cycle = WRAP_MODES
        current = cycle.index(config.line_wrap)
        return replace(config, line_wrap=cycle[(current + 1) % len(cycle)])
    if field == "verse_spacing":
        cycle = SPACING_LEVELS
        current = cycle.index(config.verse_spacing)
        return replace(config, verse_spacing=cycle[(current + 1) % len(cycle)])
    if field == "low_vision":
        return replace(config, low_vision=not config.low_vision)
    if field == "show_chapter_heading":
        return replace(config, show_chapter_heading=not config.show_chapter_heading)
    if field == "scripture_columns":
        return replace(config, scripture_columns=2 if config.scripture_columns == 1 else 1)
    return config


def _value_text(config: Config, field: str) -> str:
    if field == "low_vision":
        return "on" if config.low_vision else "off"
    if field == "show_chapter_heading":
        return "shown" if config.show_chapter_heading else "hidden"
    if field == "scripture_columns":
        return str(config.scripture_columns)
    return str(getattr(config, field))


class DisplaySettingsScreen(ModalScreen[Config]):
    DEFAULT_CSS = """
    DisplaySettingsScreen {
        align: center middle;
        background: $background 60%;
    }
    DisplaySettingsScreen OptionList {
        width: 56;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        option_list = OptionList(*self._options(), id="display-settings-list")
        option_list.border_title = "Display settings"
        option_list.border_subtitle = "Enter cycles/toggles · Esc applies and closes"
        yield option_list

    def _options(self) -> list[Option]:
        return [
            Option(f"[b]{_LABELS[field]:<18}[/] {_value_text(self.config, field)}", id=field)
            for field in _ROWS
        ]

    def on_mount(self) -> None:
        self.query_one("#display-settings-list", OptionList).focus()

    def action_cursor_down(self) -> None:
        self.query_one("#display-settings-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#display-settings-list", OptionList).action_cursor_up()

    def action_close(self) -> None:
        self.dismiss(self.config)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        field = str(event.option.id)
        self.config = _cycle_value(self.config, field)

        option_list = self.query_one("#display-settings-list", OptionList)
        highlighted = option_list.highlighted
        option_list.clear_options()
        option_list.add_options(self._options())
        option_list.highlighted = highlighted
