"""First-run setup: pick a translation, shown once per profile. Gated on
`Config.wizard_shown`, the same way `banner_shown` gates the intro
animation, and pushed before it so a first-time reader picks a
translation before seeing the banner.
"""

from __future__ import annotations

import sqlite3

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option


class WizardScreen(Screen[str]):
    """Dismisses with the chosen translation code. Escape skips with the
    current default rather than blocking a reader who just wants to get
    to the Bible."""

    BINDINGS = [Binding("escape", "skip", "Skip")]

    DEFAULT_CSS = """
    WizardScreen {
        align: center middle;
    }
    WizardScreen #wizard-box {
        width: 60;
        height: auto;
        border: round $border;
        padding: 1 2;
    }
    WizardScreen #wizard-hint {
        color: $text-muted;
        margin-bottom: 1;
    }
    """

    def __init__(self, translations: list[sqlite3.Row], default_translation: str):
        super().__init__()
        self._translations = translations
        self.translation_code = default_translation

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-box"):
            yield Static("Choose a version. Enter to confirm, esc to skip.", id="wizard-hint")
            yield OptionList(id="wizard-list")

    def on_mount(self) -> None:
        option_list = self.query_one("#wizard-list", OptionList)
        option_list.add_options(
            Option(f"[b]{t['code']}[/]  {t['name']}", id=t["code"]) for t in self._translations
        )
        option_list.highlighted = 0
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.translation_code = str(event.option.id)
        self.dismiss(self.translation_code)

    def action_skip(self) -> None:
        self.dismiss(self.translation_code)
