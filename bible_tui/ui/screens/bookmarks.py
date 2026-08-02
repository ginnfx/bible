"""Every bookmarked verse, with the tools you need once there are more than
a screenful of them: a filter, a choice of ordering, renaming and deleting.

Selecting one dismisses with its (book_id, chapter, verse) so the reader can
jump there - that return shape is what ReaderScreen already expects.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from ...data.repository import ORDER_CANONICAL, ORDER_FOLDER, ORDER_RECENT
from ...services.annotation_service import AnnotationService
from ...services.reading_list_service import ReadingListService
from .prompt import PromptModal
from .reading_lists import ReadingListsScreen

_ORDER_LABELS = {
    ORDER_RECENT: "most recent first",
    ORDER_CANONICAL: "Genesis to Revelation",
    ORDER_FOLDER: "by folder",
}
_ORDER_CYCLE = (ORDER_RECENT, ORDER_CANONICAL, ORDER_FOLDER)


class BookmarksScreen(Screen[tuple[int, int, int] | None]):
    """Browses bookmarks, or - with `favourites=True` - the separate
    favourites list. Favourite rows have no label/folder/tags of their own,
    so filing, renaming and tagging are bookmarks-only actions; the filter,
    ordering and delete-this-entry machinery is shared."""

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("ctrl+f,slash", "focus_filter", "Filter", show=False),
        Binding("o", "cycle_order", "Order"),
        Binding("l,f2", "rename", "Label"),
        Binding("f", "move_to_folder", "Folder"),
        Binding("t", "tag", "Tag"),
        Binding("d,delete", "delete", "Delete"),
        Binding("v", "toggle_favourites_view", "Favourites", show=False),
        Binding("ctrl+l", "open_reading_lists", "Reading lists", show=False),
    ]

    DEFAULT_CSS = """
    BookmarksScreen Vertical { padding: 1 2; }
    BookmarksScreen #bookmarks-count { color: $text-muted; }
    BookmarksScreen #bookmarks-filter { margin: 1 0; }
    BookmarksScreen #bookmarks-list { height: 1fr; }
    """

    def __init__(
        self,
        annotations: AnnotationService,
        reading_lists: ReadingListService | None = None,
        favourites: bool = False,
    ):
        super().__init__()
        self.annotations = annotations
        self.reading_lists = reading_lists
        self.favourites = favourites
        self.order = ORDER_RECENT
        self._bookmarks: list = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("", id="bookmarks-count")
            yield Input(placeholder="Filter by label or reference…", id="bookmarks-filter")
            yield ListView(id="bookmarks-list")
        yield Footer()

    def on_mount(self) -> None:
        self._reload()
        self.query_one("#bookmarks-list", ListView).focus()

    # ------------------------------------------------------------------

    @property
    def _needle(self) -> str:
        return self.query_one("#bookmarks-filter", Input).value

    def _favourite_rows(self, needle: str) -> list[dict]:
        """Normalised to the same shape as a bookmark row (label/folder_name
        always None) so the shared rendering and _selected() code doesn't
        need to know which list it's looking at."""
        rows = [
            {**dict(row), "label": None, "folder_name": None}
            for row in self.annotations.list_favourites()
        ]
        needle = needle.strip().lower()
        if not needle:
            return rows
        return [r for r in rows if needle in f"{r['book_name']} {r['chapter']}:{r['verse']}".lower()]

    def _reload(self, keep_index: int | None = None) -> None:
        if self.favourites:
            self._bookmarks = self._favourite_rows(self._needle)
        else:
            self._bookmarks = self.annotations.find_bookmarks(self._needle, self.order)
        list_view = self.query_one("#bookmarks-list", ListView)
        list_view.clear()

        count = self.query_one("#bookmarks-count", Static)
        noun = "favourite" if self.favourites else "bookmark"
        if not self._bookmarks:
            if self._needle:
                count.update(f"[$text-disabled]No {noun}s match that filter.[/]")
            elif self.favourites:
                count.update("[$text-disabled]No favourites yet - press '*' on a verse.[/]")
            else:
                count.update(
                    "[$text-disabled]No bookmarks yet - press 'b' on a verse to bookmark it, "
                    "or 'B' to name one.[/]"
                )
            return

        total = f"1 {noun}" if len(self._bookmarks) == 1 else f"{len(self._bookmarks)} {noun}s"
        count.update(f"{total}, {_ORDER_LABELS[self.order]}")
        for row in self._bookmarks:
            reference = f"{row['book_name']} {row['chapter']}:{row['verse']}"
            extras = []
            if row["label"]:
                extras.append(row["label"])
            if row["folder_name"]:
                extras.append(f"in {row['folder_name']}")
            tags = self.annotations.tags_for_verse(row["book_id"], row["chapter"], row["verse"])
            if tags:
                extras.append("#" + " #".join(tags))
            suffix = f"  [$text-muted] - {'; '.join(extras)}[/]" if extras else ""
            list_view.append(ListItem(Label(f"[b]{reference}[/]{suffix}")))

        # clear() leaves the cursor unset, so without this nothing is
        # highlighted and enter/d/l have no row to act on. Re-filtering keeps
        # you near where you were rather than jumping back to the top.
        list_view.index = min(keep_index or 0, len(self._bookmarks) - 1)

    def _selected(self):
        index = self.query_one("#bookmarks-list", ListView).index
        if index is None or not (0 <= index < len(self._bookmarks)):
            return None
        return self._bookmarks[index]

    # ------------------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        self._reload()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Enter in the filter box means "now let me pick one", not "search
        # again" - the list is already filtered as you type.
        self.query_one("#bookmarks-list", ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        row = self._selected()
        if row:
            self.dismiss((row["book_id"], row["chapter"], row["verse"]))

    # ------------------------------------------------------------------

    def action_close(self) -> None:
        self.dismiss(None)

    def action_focus_filter(self) -> None:
        self.query_one("#bookmarks-filter", Input).focus()

    def action_cycle_order(self) -> None:
        self.order = _ORDER_CYCLE[(_ORDER_CYCLE.index(self.order) + 1) % len(_ORDER_CYCLE)]
        self._reload()

    def action_rename(self) -> None:
        if self.favourites:
            self.notify("Favourites don't have labels - bookmark it instead ('b').")
            return
        row = self._selected()
        if row is None:
            return
        reference = f"{row['book_name']} {row['chapter']}:{row['verse']}"
        index = self.query_one("#bookmarks-list", ListView).index

        def apply(label: str | None) -> None:
            if label is None:
                return
            self.annotations.label_bookmark(row["book_id"], row["chapter"], row["verse"], label)
            self._reload(keep_index=index)

        self.app.push_screen(
            PromptModal(
                f"Label for [b]{reference}[/]",
                initial=row["label"] or "",
                placeholder="e.g. for Sunday, memorise, answered prayer",
            ),
            apply,
        )

    def action_delete(self) -> None:
        row = self._selected()
        if row is None:
            return
        index = self.query_one("#bookmarks-list", ListView).index
        if self.favourites:
            self.annotations.toggle_favourite(row["book_id"], row["chapter"], row["verse"])
        else:
            self.annotations.remove_bookmark(row["book_id"], row["chapter"], row["verse"])
        self._reload(keep_index=index)
        self.notify(f"Removed {row['book_name']} {row['chapter']}:{row['verse']}.")

    def action_toggle_favourites_view(self) -> None:
        self.favourites = not self.favourites
        self._reload()
        self.notify("Favourites" if self.favourites else "Bookmarks")

    def action_open_reading_lists(self) -> None:
        if self.reading_lists is None:
            return

        def apply(result) -> None:
            if result:
                self.dismiss(result)

        self.app.push_screen(ReadingListsScreen(self.reading_lists), apply)

    def action_move_to_folder(self) -> None:
        if self.favourites:
            self.notify("Folders are for bookmarks, not favourites.")
            return
        row = self._selected()
        if row is None:
            return
        reference = f"{row['book_name']} {row['chapter']}:{row['verse']}"
        index = self.query_one("#bookmarks-list", ListView).index

        def apply(name: str | None) -> None:
            if name is None:
                return
            folder_id = self.annotations.create_folder(name) if name.strip() else None
            self.annotations.set_bookmark_folder(row["book_id"], row["chapter"], row["verse"], folder_id)
            self._reload(keep_index=index)

        self.app.push_screen(
            PromptModal(
                f"Folder for [b]{reference}[/] (blank to unfile)",
                initial=row["folder_name"] or "",
                placeholder="e.g. Sermon prep, Memorise this month",
            ),
            apply,
        )

    def action_tag(self) -> None:
        row = self._selected()
        if row is None:
            return
        reference = f"{row['book_name']} {row['chapter']}:{row['verse']}"
        index = self.query_one("#bookmarks-list", ListView).index
        existing = self.annotations.tags_for_verse(row["book_id"], row["chapter"], row["verse"])

        def apply(text: str | None) -> None:
            if text is None:
                return
            for name in existing:
                self.annotations.untag_verse(row["book_id"], row["chapter"], row["verse"], name)
            for name in (n.strip() for n in text.split(",")):
                if name:
                    self.annotations.tag_verse(row["book_id"], row["chapter"], row["verse"], name)
            self._reload(keep_index=index)

        self.app.push_screen(
            PromptModal(
                f"Tags for [b]{reference}[/] (comma-separated)",
                initial=", ".join(existing),
                placeholder="e.g. faith, promise, memorise",
            ),
            apply,
        )
