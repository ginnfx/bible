"""A one-line prompt: a title, an input, enter to accept, escape to cancel.

Small enough to be worth having as one reusable screen rather than three
near-identical modals. Dismisses with the typed string, or ``None`` when
cancelled - so a caller can tell "cleared it" (``""``) from "changed their
mind" (``None``), which matters for anything that can be unset.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class PromptModal(ModalScreen[str | None]):
    DEFAULT_CSS = """
    PromptModal {
        align: center middle;
        background: $background 60%;
    }
    PromptModal #prompt-box {
        width: 64;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    PromptModal #prompt-input { margin-top: 1; }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, initial: str = "", placeholder: str = "") -> None:
        super().__init__()
        self.prompt_title = title
        self.initial = initial
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-box"):
            yield Static(
                f"{self.prompt_title}  [$text-disabled]enter save · esc cancel[/]"
            )
            yield Input(value=self.initial, placeholder=self.placeholder, id="prompt-input")

    def on_mount(self) -> None:
        field = self.query_one("#prompt-input", Input)
        field.focus()
        # Put the cursor at the end so editing an existing value is an edit
        # rather than a retype.
        field.action_end()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())
