"""Format picker for writing verses to a file.

Reached from search results (``ctrl+e``) and from the reader (``e``). Shows
the destination before writing, because an export that silently drops a file
somewhere is an export you have to go hunting for.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ...models.verse import Verse
from ...services import export_service


class ExportScreen(ModalScreen[str | None]):
    """Dismisses with a status message describing what happened."""

    DEFAULT_CSS = """
    ExportScreen {
        align: center middle;
        background: $background 60%;
    }
    ExportScreen OptionList {
        width: 62;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, verses: list[Verse], translation_code: str, title: str = "") -> None:
        super().__init__()
        self._verses = verses
        self._translation = translation_code
        self._title = title

    def compose(self) -> ComposeResult:
        options = OptionList(
            *[Option(f"[b]{label}[/]  ·  .{fmt}", id=fmt) for fmt, label in export_service.FORMATS],
            id="export-list",
        )
        options.border_title = f"Export {len(self._verses)} verse(s)"
        options.border_subtitle = str(export_service.DEFAULT_EXPORT_DIR)
        yield options

    def on_mount(self) -> None:
        self.query_one("#export-list", OptionList).focus()

    def action_cursor_down(self) -> None:
        self.query_one("#export-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#export-list", OptionList).action_cursor_up()

    def action_close(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        fmt = str(event.option.id)
        path = export_service.default_path(fmt, self._title or "bible")
        try:
            written = export_service.export(
                self._verses, fmt, self._translation, path, self._title
            )
        except export_service.ExportError as error:
            self.dismiss(f"Export failed - {error}")
            return
        self.dismiss(f"Exported to {written}")
