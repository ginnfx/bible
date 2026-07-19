"""Live full-text search.

Results update as you type, the highlighted one is previewed in full
underneath, and the header always says what is actually being searched - the
translation, the scope, and (when a query was rewritten to find anything)
how. A search that silently changes your query is worse than one that finds
nothing, so every rescue is announced.
"""

from __future__ import annotations

import re

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, ListItem, ListView, Static

from ...models.verse import Verse
from ...services.book_scope_service import BOOK_SCOPES
from ...services.search_service import (
    CORRECTED,
    PREFIX,
    SearchFilters,
    SearchOutcome,
    SearchService,
)
from ..theme import rich_color
from .export import ExportScreen
from .prompt import PromptModal

#: Below this, a query matches so much of the Bible that the results are
#: noise. Operators are exempt - `a NEAR/2 b` is short but precise.
MIN_QUERY_LENGTH = 3

#: Enough to scroll through without making every keystroke rebuild a
#: thousand list items.
RESULT_LIMIT = 200

#: Scopes cycled with tab, in widening-to-narrowing order - built from the
#: same canonical list the Books panel filters with (`book_scope_service`),
#: so the two "narrow what I'm looking at" features never drift apart.
_SCOPES: tuple[tuple[str, SearchFilters], ...] = tuple(
    (scope.label, SearchFilters(testament=scope.testament, category=scope.category))
    for scope in BOOK_SCOPES
)

_SYNTAX_HINT = '"phrase"  ·  OR  ·  -exclude  ·  word*  ·  a NEAR/5 b'


class SearchScreen(Screen[tuple[int, int, int] | None]):
    """Dismisses with the chosen (book_id, chapter, verse), or None."""

    DEFAULT_CSS = """
    SearchScreen { background: $background; }
    SearchScreen #search-frame {
        height: 1fr;
        border: round $border;
        background: $surface;
    }
    SearchScreen #search-input {
        height: 1;
        border: none;
        background: $surface;
        padding: 0 1;
    }
    SearchScreen #search-banner {
        height: auto;
        max-height: 2;
        padding: 0 1;
        color: $bible-search-match;
    }
    SearchScreen #search-results {
        height: 1fr;
        background: $surface;
        scrollbar-size-vertical: 1;
    }
    SearchScreen #search-results > ListItem { padding: 0 1; }
    SearchScreen #search-preview {
        height: 6;
        padding: 1 2 0 2;
        border-top: solid $border-blurred;
        background: $surface;
    }
    SearchScreen #search-status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("tab", "cycle_scope", "Scope", show=False),
        Binding("shift+tab", "cycle_scope_back", "Scope", show=False),
        Binding("ctrl+r", "show_history", "History", show=False),
        Binding("ctrl+s", "save_search", "Save search", show=False),
        Binding("ctrl+n", "refine", "Refine", show=False),
        Binding("ctrl+e", "export", "Export", show=False),
    ]

    def __init__(self, search: SearchService, translation_code: str):
        super().__init__()
        self.search = search
        self.translation_code = translation_code
        self._results: list[Verse] = []
        self._scope_index = 0
        #: Set while refining, so the next query narrows these instead of
        #: searching the whole Bible again.
        self._refine_base: list[Verse] | None = None
        self._history_mode = False
        self._history: list[str] = []
        #: How many of the rows currently shown in history mode are named
        #: saves (always listed first) versus unnamed recent queries, and
        #: the saved entries themselves (each carries its own filters).
        self._saved_count = 0
        self._saved_entries: list[dict] = []

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(id="search-frame"):
            yield Input(placeholder="Search the Bible…", id="search-input")
            yield Static("", id="search-banner")
            yield ListView(id="search-results")
            yield Static("", id="search-preview")
        yield Static("", id="search-status")

    def on_mount(self) -> None:
        self._refresh_header()
        self.query_one("#search-input", Input).focus()
        self._set_status(_SYNTAX_HINT)

    @property
    def _scope(self) -> SearchFilters:
        return _SCOPES[self._scope_index][1]

    def _refresh_header(self) -> None:
        frame = self.query_one("#search-frame")
        scope = _SCOPES[self._scope_index][0]
        if self._refine_base is not None:
            scope = f"within {len(self._refine_base)} results"
        frame.border_title = f"Search · {self.translation_code} · {scope}"
        frame.border_subtitle = (
            "tab scope · ctrl+r history · ctrl+s save · ctrl+n refine · ctrl+e export · esc close"
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        self._history_mode = False
        self._run(event.value)

    def _run(self, raw: str) -> None:
        query = raw.strip()
        results_view = self.query_one("#search-results", ListView)
        results_view.clear()
        self.query_one("#search-preview", Static).update("")
        self._set_banner("")

        # Operators make a short query meaningful, so only plain word
        # queries are held back until they're long enough to be useful.
        if len(query) < MIN_QUERY_LENGTH and query.isalnum():
            self._results = []
            self._set_status(_SYNTAX_HINT)
            return
        if not query:
            self._results = []
            self._set_status(_SYNTAX_HINT)
            return

        if self._refine_base is not None:
            outcome = self.search.search_within(
                query, self._refine_base, self.translation_code, limit=RESULT_LIMIT
            )
        else:
            outcome = self.search.search(
                query, self.translation_code, self._scope, limit=RESULT_LIMIT
            )

        self._results = outcome.results
        if not self._results:
            self._set_status(f'No results for "{query}"')
            self._suggest(query)
            return

        match_style = rich_color(self.app, "bible-search-match", "yellow")
        results_view.extend(
            ListItem(Static(_result_line(v, outcome.terms, match_style))) for v in self._results
        )
        capped = " (first page)" if len(self._results) == RESULT_LIMIT else ""
        self._set_status(f"{len(self._results)} result(s){capped}")
        self._set_banner(_explain(outcome))
        results_view.index = 0

    def _suggest(self, query: str) -> None:
        """Offer spellings when nothing matched at all."""
        last = query.split()[-1] if query.split() else ""
        alternatives = self.search.suggestions(last.strip('"*-()'))
        if alternatives:
            self._set_banner("Did you mean: " + "  ·  ".join(alternatives))

    def _set_status(self, message: str) -> None:
        self.query_one("#search-status", Static).update(message)

    def _set_banner(self, message: str) -> None:
        self.query_one("#search-banner", Static).update(message)

    # ------------------------------------------------------------------
    # Scope, history, refine, export
    # ------------------------------------------------------------------

    def action_cycle_scope(self) -> None:
        self._step_scope(1)

    def action_cycle_scope_back(self) -> None:
        self._step_scope(-1)

    def _step_scope(self, delta: int) -> None:
        # Scope and refine are alternative ways of narrowing; picking one
        # clears the other rather than silently compounding them.
        self._refine_base = None
        self._scope_index = (self._scope_index + delta) % len(_SCOPES)
        self._refresh_header()
        self._run(self.query_one("#search-input", Input).value)

    def action_show_history(self) -> None:
        saved = self.search.saved_searches()
        recent = self.search.history()
        results_view = self.query_one("#search-results", ListView)
        results_view.clear()
        self.query_one("#search-preview", Static).update("")
        if not saved and not recent:
            self._set_status("No searches yet")
            return
        self._history_mode = True
        self._saved_count = len(saved)
        # Recent history is query strings only; a saved entry is a dict
        # with its own filters. `_history` keeps just the display text so
        # `_activate` can still index into it uniformly.
        self._history = [s["query"] for s in saved] + recent
        self._saved_entries = saved
        self._results = []
        for s in saved:
            results_view.append(ListItem(Static(f"★ {s['name']} - {s['query']}")))
        for q in recent:
            results_view.append(ListItem(Static(q)))
        results_view.index = 0
        self._set_status("Saved and recent searches - enter to run one, ctrl+s to save the current one")
        self._set_banner("")

    def action_save_search(self) -> None:
        query = self.query_one("#search-input", Input).value.strip()
        if not query:
            self._set_status("Nothing to save - type a search first")
            return

        def apply(name: str | None) -> None:
            if not name:
                return
            self.search.save_search(name, query, self._scope)
            self._set_status(f"Saved as “{name}”")

        self.app.push_screen(PromptModal("Name this search", placeholder="e.g. Promises, Love"), apply)

    def action_refine(self) -> None:
        if not self._results:
            self._set_status("Nothing to refine - run a search first")
            return
        self._refine_base = list(self._results)
        self._refresh_header()
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        search_input.focus()
        self._set_status(f"Refining within {len(self._refine_base)} results")

    def action_export(self) -> None:
        if not self._results:
            self._set_status("Nothing to export - run a search first")
            return
        query = self.query_one("#search-input", Input).value.strip()

        def report(message: str | None) -> None:
            if message:
                self._set_status(message)

        self.app.push_screen(
            ExportScreen(self._results, self.translation_code, title=query or "Search results"),
            report,
        )

    # ------------------------------------------------------------------
    # Movement and selection
    #
    # The Input keeps focus so typing never breaks, which means up/down have
    # to be forwarded to the results list by hand.
    # ------------------------------------------------------------------

    def action_cursor_down(self) -> None:
        self.query_one("#search-results", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#search-results", ListView).action_cursor_up()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        preview = self.query_one("#search-preview", Static)
        index = event.list_view.index
        if self._history_mode or index is None or not (0 <= index < len(self._results)):
            preview.update("")
            return
        verse = self._results[index]
        body = Text(f"{verse.reference}\n", style="bold")
        body.append(verse.text, style="none")
        preview.update(body)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self._activate(event.list_view.index)

    def on_input_submitted(self) -> None:
        query = self.query_one("#search-input", Input).value.strip()
        if query:
            self.search.remember(query)
        self._activate(self.query_one("#search-results", ListView).index)

    def _activate(self, index: int | None) -> None:
        if index is None:
            return
        if self._history_mode:
            if not (0 <= index < len(self._history)):
                return
            search_input = self.query_one("#search-input", Input)
            search_input.value = self._history[index]
            self._history_mode = False
            if index < self._saved_count:
                # A saved entry restores its scope too, not just the query
                # text - that's the whole point of naming one.
                self._restore_saved_scope(self._saved_entries[index])
                search_input.focus()
                self._run(search_input.value)
            else:
                search_input.focus()
            return
        if 0 <= index < len(self._results):
            verse = self._results[index]
            query = self.query_one("#search-input", Input).value.strip()
            if query:
                self.search.remember(query)
            self.dismiss((verse.book_id, verse.chapter, verse.verse))

    def _restore_saved_scope(self, entry: dict) -> None:
        """Match a saved entry's filters back to one of the cyclable
        scopes. Every scope a search can be saved under comes from
        `_SCOPES` in the first place, so this always finds one; a
        defensive fallback to "whole Bible" covers a hand-edited settings
        file with a scope that no longer exists."""
        wanted = (entry.get("testament"), entry.get("category"))
        for i, (_, filters) in enumerate(_SCOPES):
            if (filters.testament, filters.category) == wanted:
                self._scope_index = i
                break
        else:
            self._scope_index = 0
        self._refine_base = None
        self._refresh_header()

    def action_cancel(self) -> None:
        if self._refine_base is not None:
            # Back out of the refinement before backing out of search.
            self._refine_base = None
            self._refresh_header()
            self._run(self.query_one("#search-input", Input).value)
            return
        self.dismiss(None)


def _explain(outcome: SearchOutcome) -> str:
    """Say out loud when the query that ran isn't the one that was typed."""
    if outcome.resolution == PREFIX:
        return "No exact match - showing words that start with what you typed"
    if outcome.resolution == CORRECTED:
        swaps = ", ".join(f"{typed} → {used}" for typed, used in outcome.corrections.items())
        return f"Searched instead for {swaps}"
    return ""


def _result_line(verse: Verse, terms: tuple[str, ...], match_style: str) -> Text:
    """Reference in bold, then the verse with the query terms picked out.

    Built as a rich Text because the line wraps: Textual's own markup opens
    a gap at each styled span when it wraps, which turns a highlighted
    result into a field of holes.
    """
    line = Text(f"{verse.reference}  ", style="bold")
    line.append(verse.text, style="none")
    offset = len(line) - len(verse.text)
    for start, end in _match_spans(verse.text, terms):
        line.stylize(match_style, offset + start, offset + end)
    return line


def _match_spans(text: str, terms: tuple[str, ...]) -> list[tuple[int, int]]:
    """Where each query term occurs, case-insensitively and as a prefix.

    Prefix matching is close enough to what FTS5's porter stemming actually
    matched ("love" finding "loved") to make the hit obvious, without
    re-implementing the stemmer.
    """
    words = [re.escape(w) for w in terms if w]
    if not words:
        return []
    pattern = re.compile(rf"\b({'|'.join(words)})\w*", re.IGNORECASE)
    return [m.span() for m in pattern.finditer(text)]
