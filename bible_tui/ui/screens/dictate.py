"""Dictation drill - type the verse from memory, see exactly where it
slipped."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from ...services.reading_mode_service import score_dictation


class DictateScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", "Done"), Binding("ctrl+r", "retry", "Retry")]

    DEFAULT_CSS = """
    DictateScreen {
        align: center middle;
        background: $background 60%;
    }
    DictateScreen #box {
        width: 76;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    DictateScreen #result {
        margin-top: 1;
    }
    """

    def __init__(self, reference: str, text: str) -> None:
        super().__init__()
        self.reference = reference
        self.text = text

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(
                f"[b]{self.reference}[/] - type it from memory, enter to check, "
                "ctrl+r to try again."
            )
            yield Input(placeholder="Start typing…", id="dictate-input")
            yield Static("", id="result")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        result = score_dictation(self.text, event.value)
        rendered = " ".join(
            f"[$success]{word}[/]" if ok else f"[$error]{word}[/]"
            for word, ok in zip(result.expected_words, result.correct)
        )
        pct = round(result.accuracy * 100)
        self.query_one("#result", Static).update(f"{rendered}\n\n{pct}% correct")

    def action_retry(self) -> None:
        field = self.query_one(Input)
        field.value = ""
        self.query_one("#result", Static).update("")
        field.focus()

    def action_close(self) -> None:
        self.dismiss(None)
