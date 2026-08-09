"""Reading-mode picker: memorise, dictate, quiz, speed-read, or listen to
the current chapter instead of just scrolling through it.

Dismisses with the chosen mode's key (or ``None`` on escape); the reader
screen owns the actual verse/chapter data, so this picker only names a
choice and hands it back rather than launching anything itself.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

from ...services import tts_service

_MODES = [
    ("memorise", "Memorise", "Words vanish a few at a time until you can say the verse cold."),
    ("dictate", "Dictate", "Type the verse from memory and see exactly where it slipped."),
    ("quiz", "Quiz", "Fill in the blank, one random verse at a time."),
    ("speed", "Speed-read", "The chapter flashed one word at a time, at a pace you set."),
    (
        "listen",
        "Read aloud",
        "Hear the chapter, hands-free."
        if tts_service.is_available()
        else "Needs macOS's `say` - not available here.",
    ),
    ("sermon", "Sermon", "The chapter, one verse at a time, large and centered."),
    ("contemplative", "Contemplative", "One verse, and a quiet timer to sit with it."),
    ("meditative", "Meditative", "Gentle auto-scroll through the chapter, hands-free."),
    (
        "prayer",
        "Prayer",
        "Guided prompts - adoration, confession, thanksgiving, supplication.",
    ),
    ("journal", "Journal", "Full-screen note-taking on the selected verse."),
    (
        "academic",
        "Academic",
        "Interlinear, commentary, and cross-references for one verse, read start to finish.",
    ),
]


class ReadingModesScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "close", "Back")]

    DEFAULT_CSS = """
    ReadingModesScreen {
        align: center middle;
        background: $background 60%;
    }
    ReadingModesScreen #modes-box {
        width: 62;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    ReadingModesScreen #modes-hint {
        color: $text-muted;
        margin-bottom: 1;
    }
    ReadingModesScreen ListView {
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="modes-box"):
            yield Static("[b]Reading modes[/]")
            yield Static("Choose one, or esc to go back.", id="modes-hint")
            yield ListView(
                *[
                    ListItem(Label(f"{label}\n[$text-muted]  {desc}[/]"), id=f"mode-{key}")
                    for key, label, desc in _MODES
                ],
                id="mode-list",
            )

    def on_mount(self) -> None:
        self.query_one("#mode-list", ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is not None and event.item.id is not None:
            self.dismiss(event.item.id.removeprefix("mode-"))

    def action_close(self) -> None:
        self.dismiss(None)
