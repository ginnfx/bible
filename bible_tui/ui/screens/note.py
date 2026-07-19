"""Note editor modal - writing or editing the note attached to a verse."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Markdown, Static, TextArea


class NoteModal(ModalScreen[str | None]):
    DEFAULT_CSS = """
    NoteModal {
        align: center middle;
        background: $background 60%;
    }
    NoteModal #note-box {
        width: 70;
        height: 16;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    NoteModal #note-area, NoteModal #note-preview {
        height: 10;
        margin-top: 1;
    }
    NoteModal #note-preview {
        overflow-y: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+p", "toggle_preview", "Preview"),
    ]

    def __init__(self, reference: str, initial_text: str = "") -> None:
        super().__init__()
        self.reference = reference
        self.initial_text = initial_text
        self._previewing = False

    def compose(self) -> ComposeResult:
        with Vertical(id="note-box"):
            yield Static(
                f"Note on [b]{self.reference}[/]  "
                "[$text-disabled]ctrl+s save · ctrl+p preview · esc cancel[/]",
                id="note-hint",
            )
            yield TextArea(self.initial_text, id="note-area")
            yield Markdown("", id="note-preview")

    def on_mount(self) -> None:
        self.query_one("#note-preview", Markdown).display = False
        self.query_one("#note-area", TextArea).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.dismiss(self.query_one("#note-area", TextArea).text)

    def action_toggle_preview(self) -> None:
        area = self.query_one("#note-area", TextArea)
        preview = self.query_one("#note-preview", Markdown)
        self._previewing = not self._previewing
        if self._previewing:
            preview.update(area.text or "*(empty)*")
        area.display = not self._previewing
        preview.display = self._previewing
        if not self._previewing:
            area.focus()
