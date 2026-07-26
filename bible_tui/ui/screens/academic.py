"""Academic reading mode: one read-only scholarly layout for a verse -
citation, interlinear breakdown, commentary, then cross-references -
assembled from exactly what `StudyScreen` already computes. Presented as
one flowing page rather than `StudyScreen`'s tabs, since this mode is
meant to be read start-to-finish, not switched between.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...models.verse import Verse
from ...services.study_service import StudyService
from ..widgets.interlinear_view import InterlinearView


class AcademicScreen(Screen[None]):
    """A scholarly one-page view of a single verse. Read-only - there's
    nothing here to select or jump from, only to read."""

    BINDINGS = [Binding("escape", "close", "Back")]

    DEFAULT_CSS = """
    AcademicScreen #academic-body { padding: 1 2; }
    AcademicScreen #academic-citation { margin-bottom: 1; }
    AcademicScreen .academic-heading { margin-top: 1; color: $text-muted; }
    """

    def __init__(self, study: StudyService, verse: Verse, translation_code: str):
        super().__init__()
        self.study = study
        self.verse = verse
        self.translation_code = translation_code

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="academic-body"):
            yield Static(
                f"[bold]{self.verse.reference}[/] ({self.translation_code})\n{self.verse.text}",
                id="academic-citation",
            )
            yield Static("[b]Interlinear[/]", classes="academic-heading")
            yield InterlinearView(id="academic-interlinear")
            yield Static("[b]Commentary[/]", classes="academic-heading")
            yield Static("", id="academic-commentary")
            yield Static("[b]Cross References[/]", classes="academic-heading")
            yield Static("", id="academic-xrefs")
        yield Footer()

    def on_mount(self) -> None:
        words = self.study.interlinear_for_verse(self.verse.book_id, self.verse.chapter, self.verse.verse)
        self.query_one("#academic-interlinear", InterlinearView).load_words(words)

        commentary = self.study.commentary(self.verse.book_id, self.verse.chapter, self.verse.verse)
        text = (
            "\n\n".join(f"[bold]{c.author}[/]\n{c.text}" for c in commentary)
            or "[dim]No commentary available.[/]"
        )
        self.query_one("#academic-commentary", Static).update(text)

        xrefs = self.study.cross_references(
            self.verse.book_id, self.verse.chapter, self.verse.verse, self.translation_code
        )
        xref_text = (
            "\n".join(f"{x.book_name} {x.chapter}:{x.verse}  [dim](votes: {x.votes})[/]" for x in xrefs)
            or "[dim]No cross references found.[/]"
        )
        self.query_one("#academic-xrefs", Static).update(xref_text)

    def action_close(self) -> None:
        self.dismiss(None)
