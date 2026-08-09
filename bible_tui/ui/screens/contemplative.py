"""Contemplative mode - one verse, and a quiet timer to sit with it.

The timer never scolds: it counts down while there's time left, and once
it reaches zero it keeps counting *up* rather than stopping or flashing a
warning - reflection doesn't have a hard deadline, the countdown is just a
suggestion for how long is reasonable to start with.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ...services.reading_mode_service import format_timer

_DEFAULT_SECONDS = 90
_STEP_SECONDS = 15
_MIN_SECONDS = 30
_MAX_SECONDS = 300


class ContemplativeScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape,enter", "close", "Done"),
        Binding("space", "toggle_pause", "Pause"),
        Binding("plus,equals_sign", "longer", "+15s"),
        Binding("minus", "shorter", "-15s"),
    ]

    DEFAULT_CSS = """
    ContemplativeScreen {
        align: center middle;
        background: $background 92%;
    }
    ContemplativeScreen #box {
        width: 70;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    ContemplativeScreen #verse-text {
        margin: 1 0;
        text-align: center;
    }
    ContemplativeScreen #timer {
        color: $text-muted;
        text-align: center;
    }
    """

    def __init__(self, reference: str, text: str) -> None:
        super().__init__()
        self.reference = reference
        self.text = text
        self.duration = _DEFAULT_SECONDS
        self.remaining = _DEFAULT_SECONDS
        self.paused = False

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(
                f"[b]{self.reference}[/]  "
                "[$text-disabled]space pause · +/- adjust · esc done[/]"
            )
            yield Static(self.text, id="verse-text")
            yield Static("", id="timer")

    def on_mount(self) -> None:
        self._redraw()
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if not self.paused:
            self.remaining -= 1
            self._redraw()

    def _redraw(self) -> None:
        status = "  ·  paused" if self.paused else ""
        self.query_one("#timer", Static).update(f"{format_timer(self.remaining)}{status}")

    def action_toggle_pause(self) -> None:
        self.paused = not self.paused
        self._redraw()

    def action_longer(self) -> None:
        if self.duration < _MAX_SECONDS:
            self.duration += _STEP_SECONDS
            self.remaining += _STEP_SECONDS
        self._redraw()

    def action_shorter(self) -> None:
        if self.duration > _MIN_SECONDS:
            self.duration -= _STEP_SECONDS
            self.remaining -= _STEP_SECONDS
        self._redraw()

    def action_close(self) -> None:
        self.dismiss(None)
