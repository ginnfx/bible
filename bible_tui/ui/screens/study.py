from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
)

from ...models.verse import Verse
from ...services.study_service import StudyService
from ..widgets.interlinear_view import InterlinearView


class StudyScreen(Screen[tuple[int, int, int] | None]):
    """Interlinear (Strong's), cross-references, and commentary for one
    verse. Selecting a cross-reference dismisses with its (book_id, chapter,
    verse) so the reader can jump there."""

    BINDINGS = [("escape", "close", "Back")]

    DEFAULT_CSS = """
    StudyScreen #tab-dictionary Vertical { padding: 1 2; height: 1fr; }
    StudyScreen #dict-filter { margin-bottom: 1; }
    StudyScreen #dict-list { height: 1fr; }
    """

    def __init__(self, study: StudyService, verse: Verse, translation_code: str):
        super().__init__()
        self.study = study
        self.verse = verse
        self.translation_code = translation_code

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"[bold]{self.verse.reference}[/]  {self.verse.text}", id="study-verse")
        with TabbedContent():
            with TabPane("Interlinear", id="tab-interlinear"):
                yield InterlinearView(id="interlinear")
            with TabPane("Cross References", id="tab-xrefs"):
                yield ListView(id="xref-list")
            with TabPane("Commentary", id="tab-commentary"):
                yield VerticalScroll(Static("", id="commentary-text"))
            with TabPane("Dictionary", id="tab-dictionary"):
                with Vertical():
                    yield Input(placeholder="Search Strong's code, word, or definition…", id="dict-filter")
                    yield ListView(id="dict-list")
        yield Footer()

    def on_mount(self) -> None:
        words = self.study.interlinear_for_verse(self.verse.book_id, self.verse.chapter, self.verse.verse)
        self.query_one(InterlinearView).load_words(words)

        self._xrefs = self.study.cross_references(
            self.verse.book_id, self.verse.chapter, self.verse.verse, self.translation_code
        )
        xref_list = self.query_one("#xref-list", ListView)
        if not self._xrefs:
            xref_list.append(ListItem(Label("[dim]No cross references found.[/]")))
        for x in self._xrefs:
            xref_list.append(ListItem(Label(f"{x.book_name} {x.chapter}:{x.verse}  [dim](votes: {x.votes})[/]")))

        commentary = self.study.commentary(self.verse.book_id, self.verse.chapter, self.verse.verse)
        text = "\n\n".join(f"[bold]{c.author}[/]\n{c.text}" for c in commentary) or "[dim]No commentary available.[/]"
        self.query_one("#commentary-text", Static).update(text)

        self._reload_dictionary()

    def _reload_dictionary(self) -> None:
        query = self.query_one("#dict-filter", Input).value
        entries = self.study.search_strongs(query)
        dict_list = self.query_one("#dict-list", ListView)
        dict_list.clear()
        if not query.strip():
            dict_list.append(
                ListItem(Label("[dim]Search a Strong's code, transliteration, or definition word "
                               "- Hebrew/Greek vocabulary, not a general Bible dictionary.[/]"))
            )
            return
        if not entries:
            dict_list.append(ListItem(Label("[dim]No matches.[/]")))
            return
        for e in entries:
            dict_list.append(
                ListItem(
                    Label(
                        f"[bold]{e.code}[/] {e.transliteration} [dim]({e.language})[/]\n"
                        f"{e.pronunciation}  {e.definition}"
                    )
                )
            )

    def action_close(self) -> None:
        self.dismiss(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "dict-filter":
            self._reload_dictionary()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "xref-list" or not self._xrefs:
            return
        index = event.list_view.index
        if index is not None and 0 <= index < len(self._xrefs):
            x = self._xrefs[index]
            self.dismiss((x.book_id, x.chapter, x.verse))
