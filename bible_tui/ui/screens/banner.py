"""Animated startup banner, ported from christ-cli's intro.

Three staged beats - the cross fades up, the wordmark fades in beneath it,
then the tagline types itself out - after which the screen dismisses itself
into the reader. Any keypress skips straight to the end, and the whole thing
plays on the first launch only (``banner_shown`` in the config); ``bible
intro`` replays it on demand.
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Static

CROSS_ART = """\
           ████╗           
           ████║           
           ████║           
   ████████████████████╗   
   ╚═══════████╔═══════╝   
           ████║           
           ████║           
           ████║           
           ████║           
           ╚═══╝           """

TITLE_ART = """\
██████╗ ██╗██████╗ ██╗     ███████╗
██╔══██╗██║██╔══██╗██║     ██╔════╝
██████╔╝██║██████╔╝██║     █████╗  
██╔══██╗██║██╔══██╗██║     ██╔══╝  
██████╔╝██║██████╔╝███████╗███████╗
╚═════╝ ╚═╝╚═════╝ ╚══════╝╚══════╝"""

TAGLINE = "The Word at your fingertips"

# Beat lengths in seconds. They sum to the full runtime of the intro.
CROSS_FADE = 0.8
TITLE_FADE = 0.7
TAGLINE_TYPE = 0.7
HOLD = 0.5


class BannerScreen(Screen[None]):
    """Plays the intro, then dismisses. Never blocks: the reader is already
    constructed behind it, so skipping is instant."""

    DEFAULT_CSS = """
    BannerScreen {
        background: $background;
        align: center middle;
    }
    BannerScreen #banner-cross {
        color: $primary;
        opacity: 0%;
        text-align: center;
        width: auto;
    }
    BannerScreen #banner-title {
        color: $accent;
        text-style: bold;
        opacity: 0%;
        text-align: center;
        width: auto;
        margin-top: 1;
    }
    BannerScreen #banner-tagline {
        color: $text-muted;
        text-align: center;
        width: auto;
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._finished = False
        self._typed = 0

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                yield Static(CROSS_ART, id="banner-cross")
            with Center():
                yield Static(TITLE_ART, id="banner-title")
            with Center():
                yield Static("", id="banner-tagline")

    def on_mount(self) -> None:
        self.query_one("#banner-cross").styles.animate("opacity", value=1.0, duration=CROSS_FADE)
        self.set_timer(CROSS_FADE, self._start_title)

    def _start_title(self) -> None:
        if self._finished:
            return
        self.query_one("#banner-title").styles.animate("opacity", value=1.0, duration=TITLE_FADE)
        self.set_timer(TITLE_FADE, self._start_tagline)

    def _start_tagline(self) -> None:
        if self._finished:
            return
        interval = TAGLINE_TYPE / max(len(TAGLINE), 1)
        self.set_interval(interval, self._type_one_character)

    def _type_one_character(self) -> None:
        if self._finished:
            return
        self._typed += 1
        self.query_one("#banner-tagline", Static).update(TAGLINE[: self._typed])
        if self._typed >= len(TAGLINE):
            self.set_timer(HOLD, self._finish)

    def _finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        # Any key skips the rest of the intro - nobody should have to sit
        # through an animation twice.
        event.stop()
        self._show_everything()
        self._finish()

    def on_click(self) -> None:
        self._show_everything()
        self._finish()

    def _show_everything(self) -> None:
        self.query_one("#banner-cross").styles.opacity = 1.0
        self.query_one("#banner-title").styles.opacity = 1.0
        self.query_one("#banner-tagline", Static).update(TAGLINE)
