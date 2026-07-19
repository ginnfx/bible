"""The three-panel browser: Books | Chapters | Scripture.

Modelled on christ-cli's reader. The two sidebars are always visible, moving
the cursor in either one *previews* that chapter in the scripture panel after
a short debounce, and Enter commits the selection and walks focus rightward.
Everything the app can do is reachable from here; ``?`` lists it all.
"""

from __future__ import annotations

import sqlite3
import time

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import ListView, OptionList, Static

from ...clipboard import ClipboardError, copy as copy_to_clipboard
from ...config import (
    Config,
    PANEL_BOOKS,
    PANEL_CHAPTERS,
    PANEL_SCRIPTURE,
    VIEW_PARAGRAPH,
    VIEW_VERSE_PER_LINE,
)
from ...data.repository import BibleRepository
from ...models.verse import Verse
from ...services import copy_service, print_service, tts_service
from ...services.annotation_service import AnnotationService
from ...services.book_scope_service import BOOK_SCOPES, breadcrumb, filter_books
from ...services.navigation_service import NavigationService
from ...services.plan_service import PlanService
from ...services.reading_list_service import ReadingListService
from ...services.search_service import SearchService
from ...services.stats_service import StatsService
from ...services.study_service import StudyService
from ..theme import next_theme
from ..widgets.panels import BookList, ChapterList
from ..widgets.paragraph_view import ParagraphView
from ..widgets.status_bar import StatusBar
from ..widgets.verse_view import VerseView
from .academic import AcademicScreen
from .bookmarks import BookmarksScreen
from .compare import CompareScreen
from .contemplative import ContemplativeScreen
from .dictate import DictateScreen
from .display_settings import DisplaySettingsScreen
from .export import ExportScreen
from .goto import GotoScreen
from .help import HelpModal
from .journal import JournalScreen
from .memorise import MemoriseScreen
from .note import NoteModal
from .plans import PlansScreen
from .prayer import PrayerScreen
from .prompt import PromptModal
from .quiz import QuizScreen
from .reading_modes import ReadingModesScreen
from .search import SearchScreen
from .sermon import SermonScreen
from .speed_read import SpeedReadScreen
from .stats import StatsScreen
from .study import StudyScreen
from .topics import TopicsScreen
from .translations import TranslationScreen

#: How long a sidebar cursor must rest before its chapter is previewed. Short
#: enough to feel immediate, long enough that holding ``j`` through Psalms
#: doesn't fire 150 chapter loads.
PREVIEW_DEBOUNCE = 0.15

#: Window in which a second ``q`` confirms the quit.
QUIT_CONFIRM_SECONDS = 2.0

#: Seconds between one-line nudges of meditative auto-scroll, and the
#: bounds/step ``+``/``-`` move it within.
_MEDITATIVE_TICK_DEFAULT = 3.0
_MEDITATIVE_TICK_STEP = 0.5
_MEDITATIVE_TICK_MIN = 1.0  # fastest
_MEDITATIVE_TICK_MAX = 6.0  # slowest

_PANEL_ORDER = (PANEL_BOOKS, PANEL_CHAPTERS, PANEL_SCRIPTURE)


class ReaderScreen(Screen):
    """Owns the current position and wires keybindings to injected services."""

    BINDINGS = [
        # Panels and movement.
        Binding("left,h", "prev_panel", "Panels", show=False),
        Binding("right,l", "next_panel", "Panels", show=False),
        Binding("down,j", "move_down", "Down", show=False),
        Binding("up,k", "move_up", "Up", show=False),
        Binding("left_square_bracket", "prev_chapter", "Prev chapter", show=False),
        Binding("right_square_bracket", "next_chapter", "Next chapter", show=False),
        Binding("alt+left", "history_back", "Back", show=False),
        Binding("alt+right", "history_forward", "Forward", show=False),
        Binding("g,ctrl+g", "open_goto", "Go to", show=False),
        Binding("tab", "cycle_books_scope", "Books scope", show=False),
        Binding("shift+tab", "cycle_books_scope_back", "Books scope", show=False),
        # Reading.
        Binding("p", "toggle_view", "View", show=False),
        Binding("v", "open_translations", "Translation", show=False),
        Binding("t", "cycle_theme", "Theme", show=False),
        Binding("f", "toggle_focus", "Focus mode", show=False),
        Binding("number_sign", "toggle_verse_numbers", "Verse numbers", show=False),
        Binding("backslash", "compare_translations", "Compare", show=False),
        Binding("r", "random_verse", "Random", show=False),
        Binding("e", "export_chapter", "Export", show=False),
        Binding("ctrl+p", "print_chapter", "Print", show=False),
        Binding("R", "open_reading_modes", "Reading modes", show=False),
        Binding("plus,equals_sign", "meditative_faster", "Meditative pace", show=False),
        Binding("minus", "meditative_slower", "Meditative pace", show=False),
        # Clipboard.
        Binding("y,c", "copy", "Copy", show=False),
        Binding("Y,C", "copy_range", "Copy range", show=False),
        Binding("escape", "cancel_range", "Cancel", show=False),
        # Study and annotation.
        Binding("s", "open_study", "Study", show=False),
        Binding("b", "toggle_bookmark", "Bookmark", show=False),
        Binding("B", "label_bookmark", "Label bookmark", show=False),
        Binding("ctrl+b", "open_bookmarks", "Bookmarks", show=False),
        Binding("L", "add_to_reading_list", "Reading list", show=False),
        Binding("ctrl+t", "open_topics", "Topics", show=False),
        Binding("D", "open_display_settings", "Display settings", show=False),
        Binding("m", "cycle_highlight", "Highlight", show=False),
        Binding("n", "edit_note", "Note", show=False),
        Binding("*", "toggle_favourite", "Favourite", show=False),
        # Search, plans, help, quit.
        Binding("slash,ctrl+f", "open_search", "Search", show=False),
        Binding("P", "open_plans", "Plans", show=False),
        Binding("S", "open_stats", "Stats", show=False),
        Binding("question_mark", "help", "Help", show=False),
        Binding("q", "quit_pending", "Quit", show=False),
    ]

    DEFAULT_CSS = """
    ReaderScreen #frame {
        border: round $border-blurred;
        background: $background;
        height: 1fr;
    }
    ReaderScreen #panels {
        height: 1fr;
    }
    ReaderScreen #book-list {
        width: auto;
        max-width: 26;
        min-width: 14;
    }
    ReaderScreen #scripture {
        width: 1fr;
        border: round $border-blurred;
        background: $surface;
    }
    ReaderScreen #scripture:focus-within {
        border: round $border;
    }
    ReaderScreen #chapter-heading {
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        text-style: bold;
    }
    ReaderScreen VerseView {
        height: 1fr;
        background: $surface;
        padding: 0 1;
        scrollbar-size-vertical: 1;
    }
    ReaderScreen ParagraphView {
        height: 1fr;
        background: $surface;
    }
    /* Focus mode: the sidebars and the outer frame get out of the way and
       scripture takes the whole terminal. */
    ReaderScreen.focus-mode #book-list,
    ReaderScreen.focus-mode #chapter-list { display: none; }
    ReaderScreen.focus-mode #frame { border: none; }
    ReaderScreen.focus-mode #scripture { border: none; }
    ReaderScreen.hide-verse-numbers VerseView .verse-number { display: none; }
    """

    def __init__(
        self,
        repo: BibleRepository,
        navigation: NavigationService,
        annotations: AnnotationService,
        study: StudyService,
        search: SearchService,
        plans: PlanService,
        stats: StatsService,
        reading_lists: ReadingListService,
        initial_position: tuple[int, int, int | None],
        view_mode: str = VIEW_VERSE_PER_LINE,
        active_panel: str = PANEL_SCRIPTURE,
    ):
        super().__init__()
        self.repo = repo
        self.navigation = navigation
        self.annotations = annotations
        self.study = study
        self.search = search
        self.plans = plans
        self.stats = stats
        self.reading_lists = reading_lists
        self.book_id, self.chapter, self._initial_verse = initial_position
        self.view_mode = view_mode
        self.active_panel = active_panel if active_panel in _PANEL_ORDER else PANEL_SCRIPTURE

        self._books = self.repo.get_all_books()
        #: Index into BOOK_SCOPES for the Books panel's `tab` filter. Purely
        #: a sidebar display concern - never touches book_id/chapter.
        self._books_scope_index = 0
        self._books_scope_suppress_timer = None
        # Tracked rather than queried on demand: the app persists it from
        # on_unmount, by which point the widget tree is already gone.
        self._current_verse = 0
        self._preview_timer = None
        # The reading clock. It runs only while this screen is the one on
        # top: seconds accumulate into _chapter_seconds and are written as a
        # single reading event when the chapter changes, so time spent in
        # search or study isn't counted as reading and a chapter read either
        # side of a modal is still one visit, not two.
        self._chapter_opened_at: float | None = None
        self._chapter_seconds = 0
        self._open_chapter: tuple[int, int, int] = (0, 0, 0)
        self._quit_armed_at: float | None = None
        self._suppress_preview = False
        self.focus_mode = False
        self.show_verse_numbers = True
        # The running `say` process for read-aloud, if one is playing -
        # tracked here (not on the picker screen, which is long gone by the
        # time this needs stopping) so R toggles play/stop in one keypress.
        self._tts_process = None
        # The running meditative-scroll interval, if one is active - same
        # toggle-by-key shape as read-aloud above.
        self._meditative_timer = None
        self._meditative_tick = _MEDITATIVE_TICK_DEFAULT

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(id="frame"):
            with Horizontal(id="panels"):
                yield BookList(self._books, id="book-list")
                yield ChapterList(id="chapter-list")
                with Vertical(id="scripture"):
                    yield Static("", id="chapter-heading")
                    yield VerseView(id="verse-view")
                    yield ParagraphView(id="paragraph-view")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#frame").border_title = "bible"
        self._apply_view_mode()
        self._sync_sidebars()
        self._load_chapter(select_verse=self._initial_verse)
        self._focus_panel(self.active_panel)
        self.query_one("#book-list", BookList).border_subtitle = "tab: filter"

    # ------------------------------------------------------------------
    # Panel focus
    # ------------------------------------------------------------------

    def _panel_widget(self, panel: str):
        if panel == PANEL_BOOKS:
            return self.query_one("#book-list", BookList)
        if panel == PANEL_CHAPTERS:
            return self.query_one("#chapter-list", ChapterList)
        return self._scripture_widget()

    def _scripture_widget(self):
        if self.view_mode == VIEW_PARAGRAPH:
            return self.query_one("#paragraph-view", ParagraphView)
        return self.query_one("#verse-view", VerseView)

    def _focus_panel(self, panel: str) -> None:
        self.active_panel = panel
        self._panel_widget(panel).focus()
        self._update_status()

    def action_prev_panel(self) -> None:
        index = _PANEL_ORDER.index(self.active_panel)
        if index > 0:
            self._focus_panel(_PANEL_ORDER[index - 1])

    def action_next_panel(self) -> None:
        index = _PANEL_ORDER.index(self.active_panel)
        if index < len(_PANEL_ORDER) - 1:
            self._focus_panel(_PANEL_ORDER[index + 1])

    # ------------------------------------------------------------------
    # Movement - j/k dispatch to whichever panel has focus
    # ------------------------------------------------------------------

    def action_move_down(self) -> None:
        self._move(1)

    def action_move_up(self) -> None:
        self._move(-1)

    def _move(self, delta: int) -> None:
        widget = self._panel_widget(self.active_panel)
        if isinstance(widget, OptionList):
            widget.action_cursor_down() if delta > 0 else widget.action_cursor_up()
        elif isinstance(widget, ListView):
            if self._continue_past_chapter_edge(widget, delta):
                return
            widget.action_cursor_down() if delta > 0 else widget.action_cursor_up()
        elif isinstance(widget, ParagraphView):
            widget.scroll_down() if delta > 0 else widget.scroll_up()

    def _continue_past_chapter_edge(self, verse_view: VerseView, delta: int) -> bool:
        """Reading off the end of a chapter carries on into the next one.

        This is what makes a book readable straight through: the cursor
        crossing the last verse loads the next chapter and lands on its
        first verse, and the same in reverse at the top. Returns True when
        it handled the move.
        """
        verses = verse_view.verses
        if not verses or verse_view.index is None or verse_view.has_range:
            return False

        if delta > 0 and verse_view.index == len(verses) - 1:
            target = self.navigation.next_chapter(self.book_id, self.chapter)
            if target:
                self._go_to(*target, keep_focus=True)
                return True
        elif delta < 0 and verse_view.index == 0:
            target = self.navigation.prev_chapter(self.book_id, self.chapter)
            if target:
                self._go_to(*target, keep_focus=True)
                self.query_one("#verse-view", VerseView).index = (
                    len(self.query_one("#verse-view", VerseView).verses) - 1
                )
                return True
        return False

    # ------------------------------------------------------------------
    # Live preview: moving a sidebar cursor loads that chapter
    # ------------------------------------------------------------------

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if self._suppress_preview:
            return
        if event.option_list.id == "book-list":
            book_id = self.query_one("#book-list", BookList).selected_book_id
            if book_id is None or book_id == self.book_id:
                return
            # Coming back to a book returns you to where you stopped in it,
            # not to chapter 1.
            remembered = self.repo.book_position(book_id)
            chapter = remembered[0] if remembered else 1
            self._reload_chapter_list(book_id, chapter)
            self._arm_preview(book_id, chapter)
        elif event.option_list.id == "chapter-list":
            chapter = self.query_one("#chapter-list", ChapterList).selected_chapter
            book_id = self.query_one("#book-list", BookList).selected_book_id or self.book_id
            if chapter is None or (book_id, chapter) == (self.book_id, self.chapter):
                return
            self._arm_preview(book_id, chapter)

    def _arm_preview(self, book_id: int, chapter: int) -> None:
        if self._preview_timer is not None:
            self._preview_timer.stop()
        self._preview_timer = self.set_timer(
            PREVIEW_DEBOUNCE, lambda: self._go_to(book_id, chapter, keep_focus=True)
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Enter commits the selection and walks focus one panel right."""
        if event.option_list.id == "book-list":
            self._focus_panel(PANEL_CHAPTERS)
        elif event.option_list.id == "chapter-list":
            chapter = self.query_one("#chapter-list", ChapterList).selected_chapter
            book_id = self.query_one("#book-list", BookList).selected_book_id or self.book_id
            if chapter is not None:
                self._go_to(book_id, chapter, keep_focus=True)
            self._focus_panel(PANEL_SCRIPTURE)

    # ------------------------------------------------------------------
    # Chapter loading
    # ------------------------------------------------------------------

    def jump(self, book_id: int, chapter: int, verse: int | None = None) -> None:
        """Entry point for other screens (search, plans, bookmarks)."""
        self._go_to(book_id, chapter, verse)

    def _go_to(
        self, book_id: int, chapter: int, verse: int | None = None, keep_focus: bool = False
    ) -> None:
        self.book_id, self.chapter = book_id, chapter
        self._sync_sidebars()
        self._load_chapter(select_verse=verse, keep_focus=keep_focus)

    def _sync_sidebars(self) -> None:
        """Point both sidebars at the current position without re-triggering
        the preview they would otherwise arm."""
        self._suppress_preview = True
        try:
            self.query_one("#book-list", BookList).select_book_id(self.book_id)
            book = self.repo.get_book(self.book_id)
            if book:
                self.query_one("#chapter-list", ChapterList).load_chapters(
                    book["chapter_count"], self.chapter
                )
        finally:
            self._suppress_preview = False

    def _reload_chapter_list(self, book_id: int, chapter: int) -> None:
        self._suppress_preview = True
        try:
            book = self.repo.get_book(book_id)
            if book:
                self.query_one("#chapter-list", ChapterList).load_chapters(
                    book["chapter_count"], chapter
                )
        finally:
            self._suppress_preview = False

    def _load_chapter(self, select_verse: int | None = None, keep_focus: bool = False) -> None:
        self.credit_time_read()
        verses = self.navigation.go_to_chapter(self.book_id, self.chapter)
        highlights = self.annotations.highlights_for_chapter(self.book_id, self.chapter)

        config = self.app.config
        verse_view = self.query_one("#verse-view", VerseView)
        verse_view.load_chapter(
            verses,
            self.annotations.bookmarks_for_chapter(self.book_id, self.chapter),
            highlights,
            self.annotations.notes_for_chapter(self.book_id, self.chapter),
            self.study.study_markers_for_chapter(self.book_id, self.chapter),
            line_wrap=config.line_wrap,
            verse_spacing=config.verse_spacing,
            low_vision=config.low_vision,
        )
        self.query_one("#paragraph-view", ParagraphView).load_chapter(
            verses, highlights, columns=config.scripture_columns
        )
        self._update_chapter_heading()

        if select_verse:
            verse_view.select_verse_number(select_verse)
        self._current_verse = verses[0].verse if verses else 0
        selected = verse_view.selected_verse
        if selected:
            self._current_verse = selected.verse
        if not keep_focus:
            self._focus_panel(PANEL_SCRIPTURE)

        self.repo.set_last_position(self.navigation.translation_code, self.book_id, self.chapter)
        self.repo.remember_book_position(self.book_id, self.chapter, self._current_verse)
        self._open_chapter = (self.book_id, self.chapter, len(verses))
        self._chapter_seconds = 0
        self._chapter_opened_at = time.monotonic()
        self._update_status()

    def _pause_clock(self) -> None:
        if self._chapter_opened_at is None:
            return
        self._chapter_seconds += int(time.monotonic() - self._chapter_opened_at)
        self._chapter_opened_at = None

    def _resume_clock(self) -> None:
        if self._chapter_opened_at is None and self._open_chapter[0]:
            self._chapter_opened_at = time.monotonic()

    def on_screen_suspend(self) -> None:
        self._pause_clock()

    def on_screen_resume(self) -> None:
        self._resume_clock()

    def credit_time_read(self) -> None:
        """Bank the chapter being left. Called when moving on and when the
        app closes; the service itself discards anything too brief to have
        been read, so paging through costs nothing."""
        self._pause_clock()
        seconds, self._chapter_seconds = self._chapter_seconds, 0
        book_id, chapter, verses = self._open_chapter
        if not seconds or not book_id:
            return
        try:
            before_coverage = self.stats.coverage()
            before_streak = self.stats.streak()
            recorded = self.stats.record(
                book_id,
                chapter,
                self.navigation.translation_code,
                seconds=seconds,
                verses=verses,
            )
            if recorded:
                for message in self.stats.check_milestones(before_coverage, before_streak):
                    self.app.notify(message, title="Milestone")
        except sqlite3.Error:
            pass  # a reading tally is never worth losing the reader's place over

    def _update_status(self) -> None:
        book = self.repo.get_book(self.book_id)
        plan_status = ""
        plan = self.plans.active_plan()
        if plan:
            plan_status = f"streak {self.plans.current_streak(plan['id'])}"

        self.query_one(StatusBar).update_status(
            f"{book['name']} {self.chapter}" if book else "",
            self.navigation.translation_code,
            self.app.theme,
            plan_status,
        )
        scripture = self.query_one("#scripture", Vertical)
        scripture.border_title = (
            f"{book['name']} {self.chapter} · {breadcrumb(book)}" if book else "Scripture"
        )

    def _update_chapter_heading(self) -> None:
        """A heading inside the scripture panel's body - distinct from the
        border-title breadcrumb above, which stays regardless."""
        heading = self.query_one("#chapter-heading", Static)
        heading.display = self.app.config.show_chapter_heading
        if heading.display:
            book = self.repo.get_book(self.book_id)
            heading.update(f"{book['name']} {self.chapter}" if book else "")

    # ------------------------------------------------------------------
    # Reading modes and appearance
    # ------------------------------------------------------------------

    def _apply_view_mode(self) -> None:
        paragraph = self.view_mode == VIEW_PARAGRAPH
        self.query_one("#verse-view", VerseView).display = not paragraph
        self.query_one("#paragraph-view", ParagraphView).display = paragraph

    def action_toggle_view(self) -> None:
        self.view_mode = (
            VIEW_VERSE_PER_LINE if self.view_mode == VIEW_PARAGRAPH else VIEW_PARAGRAPH
        )
        self.query_one("#verse-view", VerseView).clear_range()
        self._apply_view_mode()
        if self.active_panel == PANEL_SCRIPTURE:
            self._focus_panel(PANEL_SCRIPTURE)
        self._flash(
            "Paragraph view" if self.view_mode == VIEW_PARAGRAPH else "Verse-per-line view"
        )

    def action_toggle_focus(self) -> None:
        """Hide everything that isn't scripture."""
        self.focus_mode = not self.focus_mode
        self.set_class(self.focus_mode, "focus-mode")
        if self.focus_mode:
            self._focus_panel(PANEL_SCRIPTURE)
        self._flash("Focus mode on - f to leave" if self.focus_mode else "Focus mode off")

    def action_toggle_verse_numbers(self) -> None:
        self.show_verse_numbers = not self.show_verse_numbers
        self.set_class(not self.show_verse_numbers, "hide-verse-numbers")
        self._flash("Verse numbers on" if self.show_verse_numbers else "Verse numbers off")

    def action_random_verse(self) -> None:
        verse_id = self.repo.random_verse_id(self.navigation.translation_code)
        verse = self.repo.get_verse_by_id(verse_id) if verse_id else None
        if verse is None:
            self._flash("No verses available")
            return
        self._go_to(verse.book_id, verse.chapter, verse.verse)
        self._flash(f"Random - {verse.reference}")

    def action_compare_translations(self) -> None:
        verse = self._selected_verse()
        if verse is None:
            return
        renderings = self.repo.get_verse_in_every_translation(
            verse.book_id, verse.chapter, verse.verse
        )
        self.app.push_screen(CompareScreen(verse.reference, renderings))

    def action_export_chapter(self) -> None:
        """Export the visual range if one is armed, otherwise the chapter."""
        verse_view = self.query_one("#verse-view", VerseView)
        verses = verse_view.selected_verses() if verse_view.has_range else verse_view.verses
        if not verses:
            return
        book = self.repo.get_book(self.book_id)
        title = f"{book['name']} {self.chapter}" if book else "Passage"
        if verse_view.has_range and len(verses) > 1:
            title = f"{title}:{verses[0].verse}-{verses[-1].verse}"

        self.app.push_screen(
            ExportScreen(verses, self.navigation.translation_code, title),
            lambda message: self._flash(message) if message else None,
        )

    def action_print_chapter(self) -> None:
        """Print the visual range if one is armed, otherwise the chapter."""
        verse_view = self.query_one("#verse-view", VerseView)
        verses = verse_view.selected_verses() if verse_view.has_range else verse_view.verses
        if not verses:
            return
        book = self.repo.get_book(self.book_id)
        title = f"{book['name']} {self.chapter}" if book else "Passage"
        try:
            print_service.print_verses(verses, self.navigation.translation_code, title)
        except print_service.PrintUnavailable as error:
            self._flash(str(error))
        else:
            self._flash(f"Sent {title} to the printer.")

    # ------------------------------------------------------------------
    # Reading modes: memorise, dictate, quiz, speed-read, listen, sermon,
    # contemplative, meditative, prayer, journal
    # ------------------------------------------------------------------

    def action_open_reading_modes(self) -> None:
        self.app.push_screen(ReadingModesScreen(), self._launch_reading_mode)

    def _launch_reading_mode(self, mode: str | None) -> None:
        if mode == "memorise":
            self._open_verse_drill(MemoriseScreen, needs_seed=True)
        elif mode == "dictate":
            self._open_verse_drill(DictateScreen, needs_seed=False)
        elif mode == "quiz":
            self.app.push_screen(QuizScreen(self.repo, self.navigation.translation_code))
        elif mode == "speed":
            self._open_speed_read()
        elif mode == "listen":
            self._toggle_read_aloud()
        elif mode == "sermon":
            self._open_sermon()
        elif mode == "contemplative":
            self._open_verse_drill(ContemplativeScreen, needs_seed=False)
        elif mode == "meditative":
            self._toggle_meditative_scroll()
        elif mode == "prayer":
            self._open_prayer()
        elif mode == "journal":
            self._open_journal()
        elif mode == "academic":
            self._open_academic()

    def _open_prayer(self) -> None:
        verse = self._selected_verse()
        if verse is None:
            self._flash("Select a verse first")
            return
        self.app.push_screen(
            PrayerScreen(verse.reference, verse.text),
            lambda body: self._save_prayer(verse, body),
        )

    def _save_prayer(self, verse: Verse, body: str | None) -> None:
        # Always a new note - a prayer session over this verse next month
        # shouldn't erase the one from today.
        if body:
            self.annotations.add_note(verse.book_id, verse.chapter, verse.verse, body)
            self._load_chapter(select_verse=verse.verse, keep_focus=True)

    def _open_verse_drill(self, screen_cls, *, needs_seed: bool) -> None:
        verse = self._selected_verse()
        if verse is None:
            self._flash("Select a verse first")
            return
        if needs_seed:
            # Pinned to the verse's own coordinates so the same verse always
            # hides the same words in the same order, session to session.
            seed = hash((verse.book_id, verse.chapter, verse.verse)) & 0xFFFFFFFF
            self.app.push_screen(screen_cls(verse.reference, verse.text, seed))
        else:
            self.app.push_screen(screen_cls(verse.reference, verse.text))

    def _open_speed_read(self) -> None:
        verses = self.query_one("#verse-view", VerseView).verses
        if not verses:
            self._flash("Nothing to speed-read here")
            return
        text = " ".join(v.text for v in verses)
        self.app.push_screen(SpeedReadScreen(f"{verses[0].book_name} {self.chapter}", text))

    def _open_sermon(self) -> None:
        verses = self.query_one("#verse-view", VerseView).verses
        if not verses:
            self._flash("Nothing to present here")
            return
        self.app.push_screen(SermonScreen(f"{verses[0].book_name} {self.chapter}", verses))

    def _toggle_read_aloud(self) -> None:
        if self._tts_process is not None:
            self._tts_process.terminate()
            self._tts_process = None
            self._flash("Stopped reading aloud")
            return
        if not tts_service.is_available():
            self._flash("Read-aloud needs macOS's `say` command")
            return
        verses = self.query_one("#verse-view", VerseView).verses
        if not verses:
            return
        text = " ".join(v.text for v in verses)
        self._tts_process = tts_service.speak(text)
        self._flash("Reading aloud - R to stop")

    def _toggle_meditative_scroll(self) -> None:
        if self._meditative_timer is not None:
            self._meditative_timer.stop()
            self._meditative_timer = None
            self._flash("Meditative scroll stopped")
            return
        self._meditative_tick = _MEDITATIVE_TICK_DEFAULT
        self._meditative_timer = self.set_interval(self._meditative_tick, self._meditative_step)
        self._flash("Meditative scroll on - R stops it, +/- change the pace")

    def _meditative_step(self) -> None:
        widget = self._scripture_widget()
        if widget.scroll_y >= widget.max_scroll_y:
            self._meditative_timer.stop()
            self._meditative_timer = None
            self._flash("End of chapter - meditative scroll stopped")
            return
        widget.scroll_down(animate=False)

    def action_meditative_faster(self) -> None:
        self._restart_meditative_at(max(_MEDITATIVE_TICK_MIN, self._meditative_tick - _MEDITATIVE_TICK_STEP))

    def action_meditative_slower(self) -> None:
        self._restart_meditative_at(min(_MEDITATIVE_TICK_MAX, self._meditative_tick + _MEDITATIVE_TICK_STEP))

    def _restart_meditative_at(self, tick: float) -> None:
        # A no-op when meditative scrolling isn't running - +/- otherwise
        # do nothing observable, same as the other guarded actions here.
        if self._meditative_timer is None:
            return
        self._meditative_tick = tick
        self._meditative_timer.stop()
        self._meditative_timer = self.set_interval(tick, self._meditative_step)

    def on_unmount(self) -> None:
        # A `say` process outlives the screen unless told otherwise, and the
        # meditative-scroll timer would happily keep firing into whatever
        # comes next - leaving here (quit, or the app tearing down for a
        # test) shouldn't leave either running unattended.
        if self._tts_process is not None:
            self._tts_process.terminate()
            self._tts_process = None
        if self._meditative_timer is not None:
            self._meditative_timer.stop()
            self._meditative_timer = None
        if self._books_scope_suppress_timer is not None:
            self._books_scope_suppress_timer.stop()
            self._books_scope_suppress_timer = None

    def action_cycle_theme(self) -> None:
        self.app.theme = next_theme(self.app.theme)
        self._update_status()

    def action_open_translations(self) -> None:
        translations = self.repo.conn.execute(
            "SELECT * FROM translations ORDER BY id"
        ).fetchall()

        def apply(code: str | None) -> None:
            if code and code != self.navigation.translation_code:
                self.navigation.translation_code = code
                selected = self._selected_verse()
                self._load_chapter(select_verse=selected.verse if selected else None, keep_focus=True)
                self._flash(f"Translation: {code}")

        self.app.push_screen(
            TranslationScreen(translations, self.navigation.translation_code), apply
        )

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    def action_copy(self) -> None:
        verse_view = self.query_one("#verse-view", VerseView)
        translation = self.navigation.translation_code

        if self.view_mode == VIEW_PARAGRAPH:
            verses = self.query_one("#paragraph-view", ParagraphView).verses
            if not verses:
                return
            payload = copy_service.chapter_payload(verses, translation)
        else:
            selected = verse_view.selected_verses()
            if not selected:
                return
            payload = copy_service.range_payload(selected, translation)

        text, label = payload
        try:
            copy_to_clipboard(text)
        except ClipboardError:
            self._flash("Copy failed - clipboard unavailable")
            return
        verse_view.clear_range()
        self._flash(f"Copied {label}")

    def action_copy_range(self) -> None:
        if self.view_mode == VIEW_PARAGRAPH:
            self.action_copy()
            return
        verse_view = self.query_one("#verse-view", VerseView)
        if not verse_view.verses:
            return
        if not verse_view.has_range:
            verse_view.start_range()
            self._focus_panel(PANEL_SCRIPTURE)
            self._flash("Selecting range - Y copies, Esc cancels")
            return
        self.action_copy()

    def action_cancel_range(self) -> None:
        self.query_one("#verse-view", VerseView).clear_range()

    # ------------------------------------------------------------------
    # Navigation helpers
    #
    # home/end are deliberately unbound at screen level: each panel already
    # handles them the way its own content implies (Genesis/Revelation in
    # Books, first/last chapter in Chapters, first/last verse in Scripture).
    # ------------------------------------------------------------------

    def action_prev_chapter(self) -> None:
        target = self.navigation.prev_chapter(self.book_id, self.chapter)
        if target:
            self._go_to(*target, keep_focus=True)

    def action_next_chapter(self) -> None:
        target = self.navigation.next_chapter(self.book_id, self.chapter)
        if target:
            self._go_to(*target, keep_focus=True)

    def action_history_back(self) -> None:
        target = self.navigation.back()
        if target:
            self.book_id, self.chapter = target
            self._sync_sidebars()
            self._load_chapter(keep_focus=True)

    def action_history_forward(self) -> None:
        target = self.navigation.forward()
        if target:
            self.book_id, self.chapter = target
            self._sync_sidebars()
            self._load_chapter(keep_focus=True)

    def action_open_goto(self) -> None:
        self.app.push_screen(GotoScreen(self.repo), self._jump_if_result)

    def action_cycle_books_scope(self) -> None:
        self._step_books_scope(1)

    def action_cycle_books_scope_back(self) -> None:
        self._step_books_scope(-1)

    def _step_books_scope(self, delta: int) -> None:
        self._books_scope_index = (self._books_scope_index + delta) % len(BOOK_SCOPES)
        self._apply_books_scope()

    def _apply_books_scope(self) -> None:
        """Narrows what the Books panel lists to the current scope. This is
        a sidebar display change, not navigation - unlike search's own
        scope cycling (which re-runs the query eagerly, harmless there
        since "no results" is itself informative), the currently open
        book/chapter must never move just because the list around it got
        shorter. `_suppress_preview` keeps the rebuild from arming the
        debounced preview-load that a real cursor move would trigger.

        `reload()` can post more than one highlighted-change message
        (clearing the options, then re-adding them, then this method's own
        explicit `.highlighted =`), and Textual only delivers each on a
        later tick - so the flag has to stay up for the full preview
        debounce window, not just until the next refresh, or a message
        that straggles in after a `call_after_refresh` has already fired
        slips through and gets treated as a real cursor move. A held timer
        (restarted on every scope change, harmless if it overlaps a
        previous one) covers every message from this rebuild regardless of
        which tick it lands on."""
        scope = BOOK_SCOPES[self._books_scope_index]
        filtered = filter_books(self._books, scope)
        book_list = self.query_one("#book-list", BookList)
        in_scope = any(b["id"] == self.book_id for b in filtered)
        self._suppress_preview = True
        book_list.reload(filtered, selected_book_id=self.book_id if in_scope else None)
        if self._books_scope_suppress_timer is not None:
            self._books_scope_suppress_timer.stop()
        self._books_scope_suppress_timer = self.set_timer(
            PREVIEW_DEBOUNCE, self._clear_books_scope_suppress
        )
        self._update_books_scope_subtitle(scope, in_scope)

    def _clear_books_scope_suppress(self) -> None:
        self._suppress_preview = False
        self._books_scope_suppress_timer = None

    def _update_books_scope_subtitle(self, scope, in_scope: bool) -> None:
        book_list = self.query_one("#book-list", BookList)
        if scope.label == "Whole Bible":
            book_list.border_subtitle = "tab: filter"
        elif in_scope:
            book_list.border_subtitle = scope.label
        else:
            book = self.repo.get_book(self.book_id)
            excluded = f" - {book['name']} not shown" if book else ""
            book_list.border_subtitle = f"{scope.label}{excluded}"

    def action_open_search(self) -> None:
        self.app.push_screen(
            SearchScreen(self.search, self.navigation.translation_code), self._jump_if_result
        )

    def action_open_plans(self) -> None:
        self.app.push_screen(PlansScreen(self.plans), self._jump_if_result)

    def action_open_topics(self) -> None:
        self.app.push_screen(
            TopicsScreen(self.search, self.navigation.translation_code), self._jump_if_result
        )

    def action_open_display_settings(self) -> None:
        self.app.push_screen(DisplaySettingsScreen(self.app.config), self._apply_display_settings)

    def _apply_display_settings(self, updated: Config) -> None:
        previous = self.app.config
        self.app.config = updated
        if updated.low_vision and not previous.low_vision:
            self.app.theme = "high-contrast" if self.app.current_theme.dark else "daylight"
        self._load_chapter(keep_focus=True)

    def action_open_bookmarks(self) -> None:
        self.app.push_screen(
            BookmarksScreen(self.annotations, self.reading_lists), self._jump_if_result
        )

    def action_add_to_reading_list(self) -> None:
        v = self._selected_verse()
        if not v:
            return
        lists = self.reading_lists.list_lists()

        def apply(name: str | None) -> None:
            if not name:
                return
            existing = next((row for row in lists if row["name"] == name), None)
            list_id = existing["id"] if existing else self.reading_lists.create_list(name)
            self.reading_lists.add_verse(list_id, v.book_id, v.chapter, v.verse)
            self._flash(f"Added {v.reference} to {name}")

        hint = ", ".join(row["name"] for row in lists) or "e.g. Sermon prep, To read this week"
        self.app.push_screen(
            PromptModal(
                f"Reading list for [b]{v.reference}[/] (new or existing)",
                placeholder=hint,
            ),
            apply,
        )

    def _jump_if_result(self, result) -> None:
        if result:
            self._go_to(*result)

    # ------------------------------------------------------------------
    # Annotation
    # ------------------------------------------------------------------

    @property
    def current_verse_number(self) -> int:
        """The verse the cursor is on, for the session to save. 0 when the
        chapter is empty."""
        return self._current_verse

    def _selected_verse(self):
        return self.query_one("#verse-view", VerseView).selected_verse

    def action_toggle_bookmark(self) -> None:
        v = self._selected_verse()
        if v:
            self.annotations.toggle_bookmark(v.book_id, v.chapter, v.verse)
            self._load_chapter(select_verse=v.verse, keep_focus=True)

    def action_label_bookmark(self) -> None:
        """Name the verse under the cursor, bookmarking it if it wasn't
        already - a labelled verse is one you meant to keep."""
        v = self._selected_verse()
        if not v:
            return

        def apply(label: str | None) -> None:
            if label is None:
                return
            self.annotations.label_bookmark(v.book_id, v.chapter, v.verse, label)
            self._load_chapter(select_verse=v.verse, keep_focus=True)
            self._flash(f"Labelled {v.reference}" if label else f"Label cleared on {v.reference}")

        self.app.push_screen(
            PromptModal(
                f"Label for [b]{v.reference}[/]",
                initial=self.annotations.bookmark_label(v.book_id, v.chapter, v.verse),
                placeholder="e.g. for Sunday, memorise, answered prayer",
            ),
            apply,
        )

    def action_cycle_highlight(self) -> None:
        v = self._selected_verse()
        if v:
            self.annotations.cycle_highlight(v.book_id, v.chapter, v.verse)
            self._load_chapter(select_verse=v.verse, keep_focus=True)

    def action_toggle_favourite(self) -> None:
        v = self._selected_verse()
        if not v:
            return
        is_favourite = self.annotations.toggle_favourite(v.book_id, v.chapter, v.verse)
        self._load_chapter(select_verse=v.verse, keep_focus=True)
        self._flash(f"Favourited {v.reference}" if is_favourite else f"Unfavourited {v.reference}")

    def action_edit_note(self) -> None:
        v = self._selected_verse()
        if v is None:
            return
        initial = self._existing_note_body(v)
        self.app.push_screen(NoteModal(v.reference, initial), lambda body: self._apply_note(v, body))

    def _open_journal(self) -> None:
        v = self._selected_verse()
        if v is None:
            self._flash("Select a verse first")
            return
        initial = self._existing_note_body(v)
        self.app.push_screen(JournalScreen(v.reference, initial), lambda body: self._apply_note(v, body))

    def _open_academic(self) -> None:
        v = self._selected_verse()
        if v is None:
            self._flash("Select a verse first")
            return
        self.app.push_screen(AcademicScreen(self.study, v, self.navigation.translation_code))

    def _existing_note_body(self, v: Verse) -> str:
        existing = self.annotations.get_notes(v.book_id, v.chapter, v.verse)
        return existing[0]["body"] if existing else ""

    def _apply_note(self, v: Verse, body: str | None) -> None:
        """Shared save path for the note editor and Journal mode - a note
        overwrites the one note a verse already has, same as before either
        screen existed; unlike Prayer, there's only ever one to keep."""
        if body is None:
            return
        existing = self.annotations.get_notes(v.book_id, v.chapter, v.verse)
        if existing:
            self.annotations.update_note(existing[0]["id"], body)
        elif body.strip():
            self.annotations.add_note(v.book_id, v.chapter, v.verse, body)
        self._load_chapter(select_verse=v.verse, keep_focus=True)

    # ------------------------------------------------------------------
    # Study
    # ------------------------------------------------------------------

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id == "verse-view":
            verse = self._selected_verse()
            self._current_verse = verse.verse if verse else 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # VerseView binds "enter" to select-current-item itself, consuming
        # the key before a screen-level binding sees it - so enter on a verse
        # opens study through this message instead.
        if event.list_view.id == "verse-view":
            self.action_open_study()

    def action_open_study(self) -> None:
        v = self._selected_verse()
        if v is None:
            return
        self.app.push_screen(
            StudyScreen(self.study, v, self.navigation.translation_code), self._jump_if_result
        )

    # ------------------------------------------------------------------
    # Help and quit
    # ------------------------------------------------------------------

    def action_open_stats(self) -> None:
        # Bank the open chapter first, so the numbers on the screen include
        # the reading that just happened rather than lagging one chapter.
        self.credit_time_read()
        self.app.push_screen(StatsScreen(self.stats))

    def action_help(self) -> None:
        self.app.push_screen(HelpModal())

    def action_quit_pending(self) -> None:
        """``qq`` quits - one press arms, a second within the window confirms.
        A stray ``q`` in a reading app shouldn't drop you to the shell."""
        now = time.monotonic()
        if self._quit_armed_at is not None and now - self._quit_armed_at <= QUIT_CONFIRM_SECONDS:
            self.app.exit()
            return
        self._quit_armed_at = now
        self._flash("Press q again to quit")

    def _flash(self, message: str) -> None:
        self.query_one(StatusBar).flash(message)
