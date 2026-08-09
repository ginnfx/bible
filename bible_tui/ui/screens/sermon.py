"""Sermon mode - the chapter presented one verse at a time, large and
centered. Terminals have no font size of their own, so "large text" means
one thing on screen instead of a whole paragraph, at a pace the reader sets
by hand rather than a timed word stream (see speed-reading for that)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ...models.verse import Verse
from ...services.reading_mode_service import sermon_slides


class SermonScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Done"),
        Binding("space,enter,right", "next", "Next verse"),
        Binding("left,backspace", "prev", "Previous verse"),
        Binding("r", "restart", "Restart"),
    ]

    DEFAULT_CSS = """
    SermonScreen {
        align: center middle;
        background: $background 92%;
    }
    SermonScreen #title {
        text-align: center;
        width: 100%;
    }
    SermonScreen #verse-text {
        text-align: center;
        text-style: bold;
        width: 80%;
        height: 8;
        content-align: center middle;
    }
    SermonScreen #progress {
        color: $text-muted;
        text-align: center;
        width: 100%;
    }
    """

    def __init__(self, heading: str, verses: list[Verse]) -> None:
        super().__init__()
        self.heading = heading
        self.slides = sermon_slides(verses)
        self.index = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self.heading}[/]", id="title")
            yield Static("", id="verse-text")
            yield Static("", id="progress")

    def on_mount(self) -> None:
        self._redraw()

    def _redraw(self) -> None:
        number, text = self.slides[self.index]
        self.query_one("#verse-text", Static).update(f"{number}\n\n{text}")
        self.query_one("#progress", Static).update(f"{self.index + 1} / {len(self.slides)}")

    def action_next(self) -> None:
        if self.index < len(self.slides) - 1:
            self.index += 1
            self._redraw()

    def action_prev(self) -> None:
        if self.index > 0:
            self.index -= 1
            self._redraw()

    def action_restart(self) -> None:
        self.index = 0
        self._redraw()

    def action_close(self) -> None:
        self.dismiss(None)
