"""Prayer mode - guided prompts (Adoration, Confession, Thanksgiving,
Supplication) over the current verse, with room to jot a line under each.

Unlike the note editor, finishing here *adds* a new note rather than
overwriting whatever was there - a prayer session is a moment worth keeping
alongside the last one, not a document you edit in place.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea

from ...data.prayer_prompts import ACTS_PROMPTS


class PrayerScreen(ModalScreen[str | None]):
    """Dismisses with the joined text of every non-empty section (for the
    caller to save as a new note), or ``None`` if nothing was written."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+n", "next_section", "Next"),
        Binding("ctrl+p", "prev_section", "Previous"),
        Binding("ctrl+s", "finish", "Finish"),
    ]

    DEFAULT_CSS = """
    PrayerScreen {
        align: center middle;
        background: $background 60%;
    }
    PrayerScreen #box {
        width: 72;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    PrayerScreen #section {
        margin-top: 1;
        color: $accent;
        text-style: bold;
    }
    PrayerScreen #prompt {
        color: $text-muted;
        margin-bottom: 1;
    }
    PrayerScreen #entry {
        height: 6;
    }
    """

    def __init__(self, reference: str, text: str) -> None:
        super().__init__()
        self.reference = reference
        self.text = text
        self.index = 0
        #: One entry per section, kept even while stepping away from it -
        #: a TextArea only ever holds the section currently on screen.
        self._entries: list[str] = ["" for _ in ACTS_PROMPTS]

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(
                f"[b]Prayer[/] - {self.reference}  "
                "[$text-disabled]ctrl+n/p sections · ctrl+s finish · esc cancel[/]"
            )
            yield Static(self.text, id="verse-text")
            yield Static("", id="section")
            yield Static("", id="prompt")
            yield TextArea("", id="entry")

    def on_mount(self) -> None:
        self._redraw()

    def _redraw(self) -> None:
        prompt = ACTS_PROMPTS[self.index]
        self.query_one("#section", Static).update(
            f"{prompt.section}  [$text-disabled]({self.index + 1}/{len(ACTS_PROMPTS)})[/]"
        )
        self.query_one("#prompt", Static).update(prompt.prompt)
        self.query_one("#entry", TextArea).text = self._entries[self.index]
        self.query_one("#entry", TextArea).focus()

    def _stash_current_entry(self) -> None:
        self._entries[self.index] = self.query_one("#entry", TextArea).text

    def action_next_section(self) -> None:
        self._stash_current_entry()
        self.index = (self.index + 1) % len(ACTS_PROMPTS)
        self._redraw()

    def action_prev_section(self) -> None:
        self._stash_current_entry()
        self.index = (self.index - 1) % len(ACTS_PROMPTS)
        self._redraw()

    def action_finish(self) -> None:
        self._stash_current_entry()
        lines = [
            f"{prompt.section}: {entry.strip()}"
            for prompt, entry in zip(ACTS_PROMPTS, self._entries)
            if entry.strip()
        ]
        self.dismiss("\n".join(lines) if lines else None)

    def action_cancel(self) -> None:
        self.dismiss(None)
