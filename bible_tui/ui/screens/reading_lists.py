"""Ad-hoc collections of verses - a bag with a name, distinct from a
bookmark (a single marked place) and a plan (a day-scheduled pace through
whole chapters). Opened from the bookmarks browser rather than its own
top-level key, since a reader will touch this rarely.

Two screens, structurally identical to ``BookmarksScreen``: this one
lists the lists themselves; selecting one drills into its items. Picking
an item bubbles the (book_id, chapter, verse) result straight back up
through both screens to the reader, same shape ``BookmarksScreen``
already returns.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from ...services.reading_list_service import ReadingListService
from .prompt import PromptModal


class ReadingListItemsScreen(Screen[tuple[int, int, int] | None]):
    """The verses inside one reading list."""

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("ctrl+f,slash", "focus_filter", "Filter", show=False),
        Binding("d,delete", "remove", "Remove"),
    ]

    DEFAULT_CSS = """
    ReadingListItemsScreen Vertical { padding: 1 2; }
    ReadingListItemsScreen #list-items-count { color: $text-muted; }
    ReadingListItemsScreen #list-items-filter { margin: 1 0; }
    ReadingListItemsScreen #list-items-list { height: 1fr; }
    """

    def __init__(self, service: ReadingListService, list_id: int, list_name: str) -> None:
        super().__init__()
        self.service = service
        self.list_id = list_id
        self.list_name = list_name
        self._items: list = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("", id="list-items-count")
            yield Input(placeholder="Filter by reference…", id="list-items-filter")
            yield ListView(id="list-items-list")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = self.list_name
        self._reload()
        self.query_one("#list-items-list", ListView).focus()

    @property
    def _needle(self) -> str:
        return self.query_one("#list-items-filter", Input).value

    def _reload(self, keep_index: int | None = None) -> None:
        rows = self.service.items(self.list_id)
        needle = self._needle.strip().lower()
        if needle:
            rows = [r for r in rows if needle in f"{r['book_name']} {r['chapter']}:{r['verse']}".lower()]
        self._items = rows

        list_view = self.query_one("#list-items-list", ListView)
        list_view.clear()
        count = self.query_one("#list-items-count", Static)
        if not self._items:
            count.update(
                "[$text-disabled]No verses match that filter.[/]"
                if self._needle
                else "[$text-disabled]Empty - add a verse with 'L' from the reader.[/]"
            )
            return
        total = f"1 verse" if len(self._items) == 1 else f"{len(self._items)} verses"
        count.update(total)
        for row in self._items:
            reference = f"{row['book_name']} {row['chapter']}:{row['verse']}"
            list_view.append(ListItem(Label(f"[b]{reference}[/]")))
        list_view.index = min(keep_index or 0, len(self._items) - 1)

    def _selected(self):
        index = self.query_one("#list-items-list", ListView).index
        if index is None or not (0 <= index < len(self._items)):
            return None
        return self._items[index]

    def on_input_changed(self, event: Input.Changed) -> None:
        self._reload()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#list-items-list", ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        row = self._selected()
        if row:
            self.dismiss((row["book_id"], row["chapter"], row["verse"]))

    def action_close(self) -> None:
        self.dismiss(None)

    def action_focus_filter(self) -> None:
        self.query_one("#list-items-filter", Input).focus()

    def action_remove(self) -> None:
        row = self._selected()
        if row is None:
            return
        index = self.query_one("#list-items-list", ListView).index
        self.service.remove_item(row["id"])
        self._reload(keep_index=index)
        self.notify(f"Removed {row['book_name']} {row['chapter']}:{row['verse']}.")


class ReadingListsScreen(Screen[tuple[int, int, int] | None]):
    """All reading lists. Enter drills into one; results from there bubble
    straight back up to whoever opened this screen."""

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("ctrl+f,slash", "focus_filter", "Filter", show=False),
        Binding("n", "new_list", "New list"),
        Binding("l,f2", "rename", "Rename"),
        Binding("d,delete", "delete", "Delete"),
    ]

    DEFAULT_CSS = """
    ReadingListsScreen Vertical { padding: 1 2; }
    ReadingListsScreen #lists-count { color: $text-muted; }
    ReadingListsScreen #lists-filter { margin: 1 0; }
    ReadingListsScreen #lists-list { height: 1fr; }
    """

    def __init__(self, service: ReadingListService) -> None:
        super().__init__()
        self.service = service
        self._lists: list = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("", id="lists-count")
            yield Input(placeholder="Filter by name…", id="lists-filter")
            yield ListView(id="lists-list")
        yield Footer()

    def on_mount(self) -> None:
        self._reload()
        self.query_one("#lists-list", ListView).focus()

    @property
    def _needle(self) -> str:
        return self.query_one("#lists-filter", Input).value

    def _reload(self, keep_index: int | None = None) -> None:
        rows = self.service.list_lists()
        needle = self._needle.strip().lower()
        if needle:
            rows = [r for r in rows if needle in r["name"].lower()]
        self._lists = rows

        list_view = self.query_one("#lists-list", ListView)
        list_view.clear()
        count = self.query_one("#lists-count", Static)
        if not self._lists:
            count.update(
                "[$text-disabled]No lists match that filter.[/]"
                if self._needle
                else "[$text-disabled]No reading lists yet - press 'n' to make one, "
                "or 'L' on a verse in the reader.[/]"
            )
            return
        total = f"1 list" if len(self._lists) == 1 else f"{len(self._lists)} lists"
        count.update(total)
        for row in self._lists:
            count_n = len(self.service.items(row["id"]))
            verses_label = "1 verse" if count_n == 1 else f"{count_n} verses"
            list_view.append(ListItem(Label(f"[b]{row['name']}[/]  [$text-muted] - {verses_label}[/]")))
        list_view.index = min(keep_index or 0, len(self._lists) - 1)

    def _selected(self):
        index = self.query_one("#lists-list", ListView).index
        if index is None or not (0 <= index < len(self._lists)):
            return None
        return self._lists[index]

    def on_input_changed(self, event: Input.Changed) -> None:
        self._reload()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#lists-list", ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self._open_items()

    def _open_items(self) -> None:
        row = self._selected()
        if row is None:
            return

        def apply(result) -> None:
            if result:
                self.dismiss(result)
            else:
                self._reload()

        self.app.push_screen(ReadingListItemsScreen(self.service, row["id"], row["name"]), apply)

    def action_close(self) -> None:
        self.dismiss(None)

    def action_focus_filter(self) -> None:
        self.query_one("#lists-filter", Input).focus()

    def action_new_list(self) -> None:
        def apply(name: str | None) -> None:
            if not name:
                return
            self.service.create_list(name)
            self._reload()

        self.app.push_screen(
            PromptModal("New reading list", placeholder="e.g. Sermon prep, To read this week"),
            apply,
        )

    def action_rename(self) -> None:
        row = self._selected()
        if row is None:
            return
        index = self.query_one("#lists-list", ListView).index

        def apply(name: str | None) -> None:
            if not name:
                return
            self.service.rename_list(row["id"], name)
            self._reload(keep_index=index)

        self.app.push_screen(PromptModal(f"Rename [b]{row['name']}[/]", initial=row["name"]), apply)

    def action_delete(self) -> None:
        row = self._selected()
        if row is None:
            return
        index = self.query_one("#lists-list", ListView).index
        self.service.delete_list(row["id"])
        self._reload(keep_index=index)
        self.notify(f"Deleted {row['name']}.")
