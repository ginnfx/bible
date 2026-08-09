"""Journal mode - a full-screen variant of the note editor for when a
margin note isn't enough room. Same save mechanics as `NoteModal`
(overwrites the verse's one note); the reader's own `_apply_note` is the
single place either screen's result actually gets saved.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Markdown, Static, TextArea


class JournalScreen(Screen[str | None]):
    """A plain `Screen`, not a `ModalScreen` - it fills the terminal rather
    than floating a small box over the reader, because journaling wants the
    room a margin note doesn't need."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+p", "toggle_preview", "Preview"),
    ]

    DEFAULT_CSS = """
    JournalScreen {
        background: $background;
    }
    JournalScreen #frame {
        height: 1fr;
        padding: 1 2;
    }
    JournalScreen #journal-area, JournalScreen #journal-preview {
        height: 1fr;
        margin-top: 1;
    }
    JournalScreen #journal-preview {
        overflow-y: auto;
    }
    """

    def __init__(self, reference: str, initial_text: str = "") -> None:
        super().__init__()
        self.reference = reference
        self.initial_text = initial_text
        self._previewing = False

    def compose(self) -> ComposeResult:
        with Vertical(id="frame"):
            yield Static(
                f"Journal - [b]{self.reference}[/]  "
                "[$text-disabled]ctrl+s save · ctrl+p preview · esc cancel[/]"
            )
            yield TextArea(self.initial_text, id="journal-area")
            yield Markdown("", id="journal-preview")

    def on_mount(self) -> None:
        self.query_one("#journal-preview", Markdown).display = False
        self.query_one("#journal-area", TextArea).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.dismiss(self.query_one("#journal-area", TextArea).text)

    def action_toggle_preview(self) -> None:
        area = self.query_one("#journal-area", TextArea)
        preview = self.query_one("#journal-preview", Markdown)
        self._previewing = not self._previewing
        if self._previewing:
            preview.update(area.text or "*(empty)*")
        area.display = not self._previewing
        preview.display = self._previewing
        if not self._previewing:
            area.focus()
