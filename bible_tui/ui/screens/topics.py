"""A curated list of themes - pick one, get a canned search run against it.
Results render with the same match-highlighting `SearchScreen` already
uses, so there's no second results-rendering code path to maintain.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, ListItem, ListView, Static

from ...data.topic_index import TOPICS
from ...models.verse import Verse
from ...services.search_service import SearchService
from .search import _result_line


class TopicsScreen(Screen[tuple[int, int, int] | None]):
    """Enter on a topic runs its search; enter on a result jumps the
    reader there, same result shape every other browser here uses."""

    BINDINGS = [
        Binding("escape", "close", "Back"),
    ]

    DEFAULT_CSS = """
    TopicsScreen Vertical { padding: 1 2; }
    TopicsScreen #topics-hint { color: $text-muted; }
    TopicsScreen #topics-list, TopicsScreen #topic-results { height: 1fr; }
    """

    def __init__(self, search: SearchService, translation_code: str):
        super().__init__()
        self.search = search
        self.translation_code = translation_code
        self._results: list[Verse] = []
        self._showing_results = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("Pick a theme, enter to search it.", id="topics-hint")
            yield ListView(id="topics-list")
            yield ListView(id="topic-results")
        yield Footer()

    def on_mount(self) -> None:
        topics_list = self.query_one("#topics-list", ListView)
        for topic in TOPICS:
            topics_list.append(ListItem(Static(topic.name)))
        topics_list.index = 0
        self.query_one("#topic-results", ListView).display = False
        topics_list.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "topics-list":
            self._run_topic(event.list_view.index)
        elif event.list_view.id == "topic-results":
            self._select_result(event.list_view.index)

    def _run_topic(self, index: int | None) -> None:
        if index is None or not (0 <= index < len(TOPICS)):
            return
        topic = TOPICS[index]
        outcome = self.search.search(topic.query, self.translation_code)
        self._results = outcome.results

        results_view = self.query_one("#topic-results", ListView)
        results_view.clear()
        if not self._results:
            results_view.append(ListItem(Static(f"[dim]No verses found for {topic.name}.[/]")))
        else:
            for v in self._results:
                results_view.append(ListItem(Static(_result_line(v, outcome.terms, "bold"))))
            results_view.index = 0

        self.sub_title = topic.name
        self.query_one("#topics-list", ListView).display = False
        results_view.display = True
        self._showing_results = True
        results_view.focus()

    def _select_result(self, index: int | None) -> None:
        if index is None or not (0 <= index < len(self._results)):
            return
        v = self._results[index]
        self.dismiss((v.book_id, v.chapter, v.verse))

    def action_close(self) -> None:
        if self._showing_results:
            self._showing_results = False
            self.sub_title = ""
            self.query_one("#topic-results", ListView).display = False
            topics_list = self.query_one("#topics-list", ListView)
            topics_list.display = True
            topics_list.focus()
            return
        self.dismiss(None)
