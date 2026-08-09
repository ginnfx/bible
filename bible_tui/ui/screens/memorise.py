"""Memorisation drill - progressive word hiding for one verse."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ...services.reading_mode_service import MEMORISATION_STAGES, hide_words


class MemoriseScreen(ModalScreen[None]):
    """Space hides more of the verse; since :func:`hide_words` only ever
    grows the hidden set as the stage rises, repeated presses are a one-way
    ratchet toward reciting it cold rather than a reshuffle you could get
    unlucky with."""

    BINDINGS = [
        Binding("escape", "close", "Done"),
        Binding("space,enter", "advance", "Hide more"),
        Binding("r", "reset", "Reset"),
    ]

    DEFAULT_CSS = """
    MemoriseScreen {
        align: center middle;
        background: $background 60%;
    }
    MemoriseScreen #box {
        width: 72;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    MemoriseScreen #verse-text {
        margin: 1 0;
    }
    MemoriseScreen #stage {
        color: $text-muted;
    }
    """

    def __init__(self, reference: str, text: str, seed: int) -> None:
        super().__init__()
        self.reference = reference
        self.text = text
        self.seed = seed
        self.stage = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(
                f"[b]{self.reference}[/]  "
                "[$text-disabled]space hides more · r resets · esc done[/]"
            )
            yield Static("", id="verse-text")
            yield Static("", id="stage")

    def on_mount(self) -> None:
        self._redraw()

    def _redraw(self) -> None:
        self.query_one("#verse-text", Static).update(hide_words(self.text, self.stage, self.seed))
        if self.stage == 0:
            label = "Read it through once, then space to start hiding words."
        elif self.stage == MEMORISATION_STAGES:
            label = f"Stage {self.stage} of {MEMORISATION_STAGES} - recite it."
        else:
            label = f"Stage {self.stage} of {MEMORISATION_STAGES}"
        self.query_one("#stage", Static).update(label)

    def action_advance(self) -> None:
        if self.stage < MEMORISATION_STAGES:
            self.stage += 1
            self._redraw()

    def action_reset(self) -> None:
        self.stage = 0
        self._redraw()

    def action_close(self) -> None:
        self.dismiss(None)
