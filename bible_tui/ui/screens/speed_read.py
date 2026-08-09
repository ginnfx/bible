"""Speed-reading mode - the chapter flashed one word at a time (RSVP:
rapid serial visual presentation), the pace adjustable on the fly."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Static

from ...services.reading_mode_service import rsvp_words, wpm_to_seconds_per_word

_DEFAULT_WPM = 220
_WPM_STEP = 20
_MIN_WPM = 60
_MAX_WPM = 600


class SpeedReadScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Done"),
        Binding("space", "toggle_pause", "Pause"),
        Binding("plus,equals_sign", "faster", "Faster"),
        Binding("minus", "slower", "Slower"),
        Binding("r", "restart", "Restart"),
    ]

    DEFAULT_CSS = """
    SpeedReadScreen {
        align: center middle;
        background: $background 92%;
    }
    SpeedReadScreen #ref {
        text-align: center;
        width: 100%;
    }
    SpeedReadScreen #word {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 5;
        content-align: center middle;
    }
    SpeedReadScreen #pace {
        color: $text-muted;
        text-align: center;
        width: 100%;
    }
    """

    def __init__(self, reference: str, text: str) -> None:
        super().__init__()
        self.reference = reference
        self.words = rsvp_words(text)
        self.index = 0
        self.wpm = _DEFAULT_WPM
        self.paused = False
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self.reference}[/]", id="ref")
            yield Static("", id="word")
            yield Static("", id="pace")

    def on_mount(self) -> None:
        self._show_word()
        self._schedule_next()

    def _schedule_next(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self.paused or self.index >= len(self.words):
            return
        self._timer = self.set_timer(wpm_to_seconds_per_word(self.wpm), self._advance)

    def _advance(self) -> None:
        self.index += 1
        self._show_word()
        self._schedule_next()

    def _show_word(self) -> None:
        done = self.index >= len(self.words)
        word = "· done ·" if done else self.words[self.index]
        self.query_one("#word", Static).update(word)
        shown = min(self.index, len(self.words))
        status = "  ·  paused" if self.paused and not done else ""
        self.query_one("#pace", Static).update(
            f"{self.wpm} wpm  ·  {shown}/{len(self.words)}{status}"
        )

    def action_toggle_pause(self) -> None:
        self.paused = not self.paused
        self._show_word()
        self._schedule_next()

    def action_faster(self) -> None:
        self.wpm = min(_MAX_WPM, self.wpm + _WPM_STEP)
        self._show_word()

    def action_slower(self) -> None:
        self.wpm = max(_MIN_WPM, self.wpm - _WPM_STEP)
        self._show_word()

    def action_restart(self) -> None:
        self.index = 0
        self.paused = False
        self._show_word()
        self._schedule_next()

    def action_close(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        self.dismiss(None)
