from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

from textual.app import App
from textual.message import Message

from .config import Config
from .data.database import connect, init_schema
from .data.reference_parser import parse_reference
from .data.repository import BibleRepository
from .services.annotation_service import AnnotationService
from .services.navigation_service import NavigationService
from .services.plan_service import PlanService
from .services.reading_list_service import ReadingListService
from .services.search_service import SearchService
from .services.stats_service import StatsService
from .services.study_service import StudyService
from .ui.screens.banner import BannerScreen
from .ui.screens.reader import ReaderScreen
from .ui.screens.wizard import WizardScreen
from .ui.theme import PALETTES, THEME_VARIABLE_DEFAULTS, theme_for_hour

THEMES_CSS = Path(__file__).parent / "ui" / "themes.tcss"

#: How often automatic night mode re-checks the clock.
NIGHT_CHECK_SECONDS = 900

#: Long enough for the reader to paint before the database is verified.
INTEGRITY_CHECK_DELAY = 0.5


class DatabaseDamaged(Message):
    """Raised by the launch integrity check when the database is not sound."""

    def __init__(self, summary: str) -> None:
        super().__init__()
        self.summary = summary


class BibleApp(App):
    """Composition root. Owns the DB connection and all services; screens
    receive what they need via constructor injection rather than reaching
    through self.app."""

    CSS_PATH = str(THEMES_CSS)
    TITLE = "bible"

    # This app is entirely keybinding-driven (``?`` lists everything) -
    # Textual's built-in command palette would only shadow ctrl+p, which
    # the note/journal editors use for their Markdown preview toggle.
    ENABLE_COMMAND_PALETTE = False

    # The reader owns every keybinding, including quit (qq) - a bare ctrl+q
    # here would shadow the confirmation.
    BINDINGS = []

    def __init__(
        self,
        initial_reference: str | None = None,
        force_banner: bool | None = None,
        profile: str | None = None,
    ):
        super().__init__()
        self.config = Config.load(profile)
        self.conn = connect(self.config.db_path)
        init_schema(self.conn)
        self.repo = BibleRepository(self.conn)

        self.navigation = NavigationService(self.repo, self.config.translation_code)
        self.search = SearchService(self.repo)
        self.annotations = AnnotationService(self.repo)
        self.plans = PlanService(self.conn)
        self.reading_lists = ReadingListService(self.repo)
        self.study = StudyService(self.repo)
        self.stats = StatsService(self.conn)

        self._initial_reference = initial_reference
        self._force_banner = force_banner
        self.reader_screen: ReaderScreen | None = None

        # Themes have to be live before the stylesheet is parsed, not at
        # mount time - CSS referencing a theme variable that isn't defined
        # yet fails to parse rather than falling back.
        for palette in PALETTES:
            self.register_theme(palette.theme)
        self.theme = (
            theme_for_hour(dt.datetime.now().hour)
            if self.config.auto_night_mode
            else self.config.theme
        )

    def get_theme_variable_defaults(self) -> dict[str, str]:
        return THEME_VARIABLE_DEFAULTS

    def on_mount(self) -> None:
        self.reader_screen = ReaderScreen(
            repo=self.repo,
            navigation=self.navigation,
            annotations=self.annotations,
            study=self.study,
            search=self.search,
            plans=self.plans,
            stats=self.stats,
            reading_lists=self.reading_lists,
            initial_position=self._resolve_initial_position(),
            view_mode=self.config.view_mode,
            active_panel=self.config.active_panel,
        )
        self.push_screen(self.reader_screen)

        if not self.config.wizard_shown:
            self._show_wizard()
        else:
            self._after_wizard()

        if self.config.auto_night_mode:
            # Re-check on the quarter hour so a long session crosses over
            # without being restarted.
            self.set_interval(NIGHT_CHECK_SECONDS, self._follow_the_clock)

        # Deferred and off-thread: the check takes about a third of a
        # second on a full database, and run on the event loop that is a
        # third of a second where a keypress goes unanswered.
        self.set_timer(INTEGRITY_CHECK_DELAY, self._start_integrity_check)

    def _start_integrity_check(self) -> None:
        self.run_worker(self._warn_if_damaged, thread=True, name="integrity")

    def _warn_if_damaged(self) -> None:
        """A quick check on every launch, so corruption surfaces the day it
        happens rather than the day someone reaches for a lost note. It is
        only a warning - the app still opens, because a partly-readable
        database is better than none.

        Runs on its own connection: sharing the reader's would put two
        threads on one sqlite handle for no benefit.
        """
        from .data.database import connect
        from .services.backup_service import BackupService

        try:
            conn = connect(self.config.db_path)
        except sqlite3.Error as error:
            self._report_damage(f"Could not open the database: {error}")
            return
        try:
            report = BackupService(conn).check()
        finally:
            conn.close()

        if not report.ok:
            self._report_damage(report.summary())

    def _report_damage(self, summary: str) -> None:
        # Posted rather than notified directly: this is found on a worker
        # thread, and post_message is the thread-safe way back onto the
        # event loop.
        self.post_message(DatabaseDamaged(summary))

    def on_database_damaged(self, event: DatabaseDamaged) -> None:
        self.notify(
            f"{event.summary} Run `bible check` for detail, "
            "or `bible restore <path>` to recover.",
            title="Database problem",
            severity="error",
            timeout=15,
        )

    def _follow_the_clock(self) -> None:
        wanted = theme_for_hour(dt.datetime.now().hour)
        if self.theme != wanted:
            self.theme = wanted

    def _show_wizard(self) -> None:
        translations = self.conn.execute("SELECT * FROM translations ORDER BY id").fetchall()

        def apply(translation_code: str | None) -> None:
            self.config.wizard_shown = True
            if translation_code:
                self.navigation.translation_code = translation_code
            self._after_wizard()

        self.push_screen(WizardScreen(translations, self.navigation.translation_code), apply)

    def _after_wizard(self) -> None:
        """Whatever happens once first-run setup is behind us - the intro
        banner (a later launch, not first-run at all) and the plan
        reminder both wait for this so the wizard is never fighting
        another screen for the very first frame."""
        if self._should_show_banner():
            self.push_screen(BannerScreen())
        self._remind_if_behind_on_plan()

    def _remind_if_behind_on_plan(self) -> None:
        """A friendly toast, not a blocking modal - a reader who's behind
        already knows; this is a nudge, not a scold."""
        plan = self.plans.active_plan()
        if plan is None:
            return
        behind = self.plans.days_behind(plan["id"])
        if behind > 0:
            day_word = "day" if behind == 1 else "days"
            self.notify(
                f"{behind} {day_word} behind on {plan['name']} - press P to catch up.",
                title="Reading plan",
            )

    def _should_show_banner(self) -> bool:
        """The intro plays on the first launch only. ``--banner``/``bible
        intro`` forces it on, ``--no-banner`` forces it off, and jumping
        straight to a reference always skips it."""
        if self._force_banner is not None:
            return self._force_banner
        if self._initial_reference:
            return False
        return not self.config.banner_shown

    def _resolve_initial_position(self) -> tuple[int, int, int | None]:
        if self._initial_reference:
            parsed = parse_reference(self._initial_reference)
            if parsed:
                book = self.repo.get_book_by_name_or_abbrev(parsed.book_query)
                if book:
                    return (book["id"], parsed.chapter or 1, parsed.verse_start)

        last = self.repo.get_last_position()
        if last:
            self.navigation.translation_code = last["translation_code"]
            return (last["book_id"], last["chapter"], self.config.selected_verse or None)

        genesis = self.repo.get_book_by_name_or_abbrev("Genesis")
        return (genesis["id"], 1, None) if genesis else (1, 1, None)

    def on_unmount(self) -> None:
        """Persist the whole session - translation, theme, reading mode, and
        which panel was focused - so the next launch resumes exactly here."""
        self.config.translation_code = self.navigation.translation_code
        if not self.config.auto_night_mode:
            # Under auto night mode the theme belongs to the clock, so
            # saving it would overwrite the reader's own choice.
            self.config.theme = self.theme
        self.config.banner_shown = True
        if self.reader_screen is not None:
            # The chapter open right now has never been banked; without this
            # the last (and often longest) read of every session is lost.
            self.reader_screen.credit_time_read()
            self.config.view_mode = self.reader_screen.view_mode
            self.config.active_panel = self.reader_screen.active_panel
            self.config.selected_verse = self.reader_screen.current_verse_number
        self.config.save()
        self.conn.close()
