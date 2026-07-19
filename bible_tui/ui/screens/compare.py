"""One verse, side by side in every translation.

Switching translations with ``v`` shows you a different rendering; it never
lets you see two at once, which is the whole point of having three. This
screen stacks them so the differences read at a glance, and copying takes
the whole comparison.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ...clipboard import ClipboardError, copy as copy_to_clipboard
from ...models.verse import Verse


class CompareScreen(Screen[None]):
    """Read-only comparison of one verse across the installed translations."""

    DEFAULT_CSS = """
    CompareScreen { background: $background; }
    CompareScreen #compare-frame {
        height: 1fr;
        border: round $border;
        background: $surface;
    }
    CompareScreen #compare-scroll {
        height: 1fr;
        padding: 1 2;
        scrollbar-size-vertical: 1;
    }
    CompareScreen .compare-code {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }
    CompareScreen .compare-name {
        color: $text-disabled;
    }
    CompareScreen .compare-text {
        width: 1fr;
        margin-bottom: 1;
        padding-left: 2;
    }
    CompareScreen #compare-status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape,backslash", "close", "Back"),
        Binding("y,c", "copy", "Copy all", show=False),
        Binding("down,j", "scroll_down", "Down", show=False),
        Binding("up,k", "scroll_up", "Up", show=False),
    ]

    def __init__(self, reference: str, renderings: list[tuple[str, str, Verse | None]]) -> None:
        """`renderings` is (code, full name, verse-or-None) per translation."""
        super().__init__()
        self.reference = reference
        self._renderings = renderings

    def compose(self) -> ComposeResult:
        with Vertical(id="compare-frame"):
            with VerticalScroll(id="compare-scroll"):
                for code, name, verse in self._renderings:
                    yield Static(code, classes="compare-code")
                    yield Static(name, classes="compare-name")
                    yield Static(
                        Text(verse.text if verse else "Not available in this translation."),
                        classes="compare-text",
                    )
        yield Static("", id="compare-status")

    def on_mount(self) -> None:
        frame = self.query_one("#compare-frame")
        frame.border_title = f"Compare · {self.reference}"
        frame.border_subtitle = "y copy all · esc back"
        self.query_one("#compare-scroll", VerticalScroll).focus()
        available = sum(1 for _, _, v in self._renderings if v)
        self._status(f"{available} of {len(self._renderings)} translations")

    def _status(self, message: str) -> None:
        self.query_one("#compare-status", Static).update(message)

    def action_scroll_down(self) -> None:
        self.query_one("#compare-scroll", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#compare-scroll", VerticalScroll).scroll_up()

    def action_copy(self) -> None:
        lines = [self.reference, ""]
        for code, _, verse in self._renderings:
            if verse:
                lines.append(f"{code}: {verse.text}")
        try:
            copy_to_clipboard("\n".join(lines) + "\n")
        except ClipboardError:
            self._status("Copy failed - clipboard unavailable")
            return
        self._status(f"Copied {self.reference} in {len(lines) - 2} translations")

    def action_close(self) -> None:
        self.dismiss(None)
