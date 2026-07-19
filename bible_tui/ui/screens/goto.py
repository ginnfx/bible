from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from ...data.reference_parser import parse_reference
from ...data.repository import BibleRepository


class GotoScreen(ModalScreen[tuple[int, int, int | None] | None]):
    """Modal command-line-style reference input: 'John 3:16', 'gen 1',
    '1 cor 13:4-7'. Dismisses with (book_id, chapter, verse_or_None), or
    None if cancelled."""

    DEFAULT_CSS = """
    GotoScreen {
        align: center middle;
        background: $background 60%;
    }
    #goto-box {
        width: 60;
        height: auto;
        border: round $border;
        padding: 1 2;
        background: $surface;
    }
    #goto-error {
        color: $error;
        height: auto;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, repo: BibleRepository):
        super().__init__()
        self.repo = repo

    def compose(self) -> ComposeResult:
        with Vertical(id="goto-box"):
            yield Static("Go to reference:")
            yield Input(placeholder="e.g. John 3:16, gen 1, 1 cor 13:4-7", id="goto-input")
            yield Static("", id="goto-error")

    def on_mount(self) -> None:
        self.query_one("#goto-input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value
        parsed = parse_reference(raw)
        error = self.query_one("#goto-error", Static)
        if parsed is None:
            error.update(f"[red]Couldn't parse '{raw}'.[/]")
            return
        book_row = self.repo.get_book_by_name_or_abbrev(parsed.book_query)
        if book_row is None:
            suggestions = self.repo.suggest_books(parsed.book_query)
            if suggestions:
                error.update(f"[red]No such book. Did you mean {suggestions[0]}?[/]")
            else:
                error.update(f"[red]No book matches '{parsed.book_query}'.[/]")
            return
        chapter = parsed.chapter or 1
        if chapter < 1 or chapter > book_row["chapter_count"]:
            error.update(f"[red]{book_row['name']} only has {book_row['chapter_count']} chapters.[/]")
            return
        self.dismiss((book_row["id"], chapter, parsed.verse_start))
