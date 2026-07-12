from __future__ import annotations

from textual.widgets import Static

from ..theme import label_for

#: Seconds a flash message replaces the hint row for.
FLASH_SECONDS = 2.0


class StatusBar(Static):
    """The single-line footer: current reference, then the keybinding hints.

    A flash message (a copy confirmation, a failure) takes over the whole bar
    for a couple of seconds - appended after the hints it would be clipped
    off-screen on ordinary terminal widths.
    """

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $background;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", markup=True, **kwargs)
        self._reference = ""
        self._translation = "KJV"
        self._theme = "slate"
        self._plan_status = ""
        self._flash: str | None = None
        self._flash_timer = None

    def update_status(
        self,
        reference: str,
        translation_code: str,
        theme_name: str,
        plan_status: str = "",
    ) -> None:
        self._reference = reference
        self._translation = translation_code
        self._theme = theme_name
        self._plan_status = plan_status
        self._redraw()

    def flash(self, message: str) -> None:
        self._flash = message
        if self._flash_timer is not None:
            self._flash_timer.stop()
        self._flash_timer = self.set_timer(FLASH_SECONDS, self._clear_flash)
        self._redraw()

    def _clear_flash(self) -> None:
        self._flash = None
        self._flash_timer = None
        self._redraw()

    def _redraw(self) -> None:
        if self._flash:
            self.update(f"[b $bible-search-match]{self._flash}[/]")
            return
        self.update(self._hint_row())

    def _hint_row(self) -> str:
        hints = [
            ("←→/hl", "panels"),
            ("↑↓/jk", "move"),
            ("/", "search"),
            ("y/Y", "copy"),
            ("p", "view"),
            ("t", label_for(self._theme)),
            ("v", self._translation),
            ("?", "help"),
            ("qq", "quit"),
        ]
        rendered = "  ".join(
            f"[b $primary]{key}[/] [$bible-dim]{desc}[/]" for key, desc in hints
        )
        prefix = f"[b]{self._reference}[/]  " if self._reference else ""
        if self._plan_status:
            prefix += f"[$bible-search-match]{self._plan_status}[/]  "
        return f"{prefix}{rendered}"
