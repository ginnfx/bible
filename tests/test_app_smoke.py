"""Integration tests driving the real app through Textual's Pilot harness.

These verify that keybindings reach the right handler and that the
three-panel browser wires together - not business logic, which is covered at
the service layer. They need a fully-populated bible.db (real books and
verses) rather than the minimal in-memory fixture the service tests use, so
they reuse whatever `scripts/import_data.py` already built locally and skip
otherwise instead of re-running a multi-minute import in CI.
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import replace

import pytest

from bible_tui.app import BibleApp
from bible_tui.config import (
    DEFAULT_DB_PATH,
    PANEL_BOOKS,
    PANEL_CHAPTERS,
    PANEL_SCRIPTURE,
    VIEW_PARAGRAPH,
)
from bible_tui.ui.screens.banner import BannerScreen
from bible_tui.ui.screens.help import HelpModal
from bible_tui.ui.screens.reader import ReaderScreen
from bible_tui.ui.widgets.panels import BookList, ChapterList
from bible_tui.ui.widgets.verse_view import VerseView

pytestmark = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(), reason="requires a built bible.db (run scripts/import_data.py)"
)


@pytest.fixture
def make_app(tmp_path, monkeypatch):
    """Builds apps against a throwaway copy of the real database.

    Config.save() writes to the module-level CONFIG_PATH constant rather than
    anything on the instance, so that has to be redirected too - otherwise
    on_unmount() would stamp this test's tmp db_path over the developer's
    real config.yaml on every run.
    """
    import bible_tui.config as config_module
    from bible_tui.config import Config

    db_path = tmp_path / "bible.db"
    shutil.copy(DEFAULT_DB_PATH, db_path)
    # The copy inherits whatever the developer's own real reading history
    # happens to be - position, stats, and per-book bookmarks the app has
    # accumulated from actual use. These tests assume a fresh install, so
    # clear that rather than let a personal reading session make them flaky.
    scratch = sqlite3.connect(db_path)
    scratch.execute("DELETE FROM last_position")
    scratch.execute("DELETE FROM reading_events")
    # The generic key/value settings table is where book positions, search
    # history, saved searches, milestones-fired state, and reading goals
    # all live - wiping it wholesale (rather than naming each key) means a
    # future settings-backed feature can't reintroduce this same leak.
    scratch.execute("DELETE FROM settings")
    scratch.commit()
    scratch.close()
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "config.yaml")

    # Real loading (so a second launch in one test resumes the first one's
    # session), with only the database redirected at the throwaway copy.
    # `wizard_shown=True` by default - these tests are exercising an
    # already-set-up install, not first-run onboarding; tests of the
    # wizard itself override it back to False explicitly.
    real_load = Config.load.__func__
    monkeypatch.setattr(
        Config,
        "load",
        classmethod(
            lambda cls, profile=None: replace(
                real_load(cls, profile), db_path=db_path, wizard_shown=True
            )
        ),
    )

    def build(**kwargs) -> BibleApp:
        kwargs.setdefault("force_banner", False)
        return BibleApp(**kwargs)

    return build


@pytest.fixture
def app(make_app):
    return make_app()


# ----------------------------------------------------------------------
# Launch
# ----------------------------------------------------------------------


async def test_app_boots_straight_into_the_reader(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_banner_plays_on_first_launch_and_any_key_skips_it(make_app):
    app = make_app(force_banner=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, BannerScreen)
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_explicit_reference_skips_the_banner_and_lands_there(make_app):
    app = make_app(initial_reference="John 3:16", force_banner=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)
        assert (app.screen.book_id, app.screen.chapter) == (43, 3)


async def test_the_wizard_shows_on_a_genuinely_first_launch(make_app, monkeypatch):
    from bible_tui.config import Config
    from bible_tui.ui.screens.wizard import WizardScreen

    # make_app's own patch already redirects db_path at the throwaway copy
    # and forces wizard_shown=True; layer one more patch on top that keeps
    # the throwaway db_path but flips wizard_shown back to False, so this
    # test alone exercises first-run onboarding without touching real state.
    already_patched = Config.load.__func__
    monkeypatch.setattr(
        Config,
        "load",
        classmethod(lambda cls, profile=None: replace(already_patched(cls, profile), wizard_shown=False)),
    )
    app = make_app(force_banner=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, WizardScreen)

        await pilot.press("down")  # second translation
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ReaderScreen)
        assert app.config.wizard_shown is True


async def test_escaping_the_wizard_still_finishes_it(make_app, monkeypatch):
    from bible_tui.config import Config
    from bible_tui.ui.screens.wizard import WizardScreen

    already_patched = Config.load.__func__
    monkeypatch.setattr(
        Config,
        "load",
        classmethod(lambda cls, profile=None: replace(already_patched(cls, profile), wizard_shown=False)),
    )
    app = make_app(force_banner=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, WizardScreen)
        await pilot.press("escape")  # skip, finishes
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)
        assert app.config.wizard_shown is True


async def test_a_second_launch_does_not_show_the_wizard_again(app):
    from bible_tui.ui.screens.wizard import WizardScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        assert not isinstance(app.screen, WizardScreen)


# ----------------------------------------------------------------------
# Three-panel navigation
# ----------------------------------------------------------------------


async def test_h_and_l_walk_between_the_three_panels(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert screen.active_panel == PANEL_SCRIPTURE

        await pilot.press("h")
        await pilot.pause()
        assert screen.active_panel == PANEL_CHAPTERS

        await pilot.press("h")
        await pilot.pause()
        assert screen.active_panel == PANEL_BOOKS

        # The left edge holds rather than wrapping around.
        await pilot.press("h")
        await pilot.pause()
        assert screen.active_panel == PANEL_BOOKS

        await pilot.press("l")
        await pilot.pause()
        assert screen.active_panel == PANEL_CHAPTERS


async def test_moving_the_book_cursor_previews_that_book(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("h", "h")  # focus Books
        await pilot.press("j")  # Genesis -> Exodus
        await pilot.pause(0.3)  # let the preview debounce elapse
        assert screen.book_id == 2
        assert screen.chapter == 1


async def test_moving_the_chapter_cursor_previews_that_chapter(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("h")  # focus Chapters
        await pilot.press("j")  # chapter 1 -> 2
        await pilot.pause(0.3)
        assert (screen.book_id, screen.chapter) == (1, 2)


async def test_sidebars_follow_a_jump_made_from_elsewhere(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.jump(43, 3, 16)
        await pilot.pause()
        assert screen.query_one("#book-list", BookList).selected_book_id == 43
        assert screen.query_one("#chapter-list", ChapterList).selected_chapter == 3


async def test_end_in_the_chapters_panel_previews_the_last_chapter(app):
    # home/end belong to the focused panel, so "last chapter" is reached by
    # moving to Chapters and pressing end - not by a screen-wide binding.
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("h")  # focus Chapters
        await pilot.press("end")
        await pilot.pause(0.3)
        assert (screen.book_id, screen.chapter) == (1, 50)


# ----------------------------------------------------------------------
# Reading modes and appearance
# ----------------------------------------------------------------------


async def test_p_toggles_paragraph_view(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("p")
        await pilot.pause()
        assert screen.view_mode == VIEW_PARAGRAPH
        assert screen.query_one("#paragraph-view").display is True
        assert screen.query_one("#verse-view").display is False


async def test_t_cycles_the_theme(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "slate"
        await pilot.press("t")
        await pilot.pause()
        assert app.theme == "midnight"


# ----------------------------------------------------------------------
# Clipboard
# ----------------------------------------------------------------------


async def test_y_copies_the_selected_verse(app, monkeypatch):
    copied: list[str] = []
    monkeypatch.setattr("bible_tui.ui.screens.reader.copy_to_clipboard", copied.append)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()

    assert copied == ["Genesis 1:1 - In the beginning God created the heaven and the earth. (KJV)"]


async def test_capital_y_starts_a_range_then_copies_it(app, monkeypatch):
    copied: list[str] = []
    monkeypatch.setattr("bible_tui.ui.screens.reader.copy_to_clipboard", copied.append)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("Y")  # arm the range on verse 1
        await pilot.pause()
        await pilot.press("j")  # extend to verse 2
        await pilot.pause()
        await pilot.press("Y")  # copy
        await pilot.pause()

    assert len(copied) == 1
    assert copied[0].startswith("Genesis 1:1-2 (KJV)\n")
    assert "\n1 In the beginning" in copied[0]


async def test_escape_cancels_a_pending_range(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        verse_view = app.screen.query_one(VerseView)
        await pilot.press("Y")
        await pilot.pause()
        assert verse_view.has_range is True
        await pilot.press("escape")
        await pilot.pause()
        assert verse_view.has_range is False


# ----------------------------------------------------------------------
# Annotation, study, search
# ----------------------------------------------------------------------


async def test_b_toggles_a_bookmark_marker(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        first_item = app.screen.query_one(VerseView).children[0]
        rendered = " ".join(str(child.content) for child in first_item.children)
        assert "★" in rendered


async def test_enter_on_a_verse_opens_study(app):
    from bible_tui.ui.screens.study import StudyScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")  # verse 2
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, StudyScreen)
        assert app.screen.verse.verse == 2


async def test_a_verse_with_cross_references_gets_a_footnote_marker(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        app.repo.conn.execute(
            "INSERT INTO cross_references "
            "(from_book_id, from_chapter, from_verse, to_book_id, to_chapter, to_verse) "
            "VALUES (1, 1, 1, 43, 3, 16)"
        )
        app.repo.conn.commit()

        await pilot.press("]")  # next chapter and back, to force a reload
        await pilot.press("[")
        await pilot.pause()

        first_item = app.screen.query_one(VerseView).children[0]
        rendered = " ".join(str(child.content) for child in first_item.children)
        assert "†" in rendered


async def test_the_dictionary_tab_searches_strongs_entries(app):
    from textual.widgets import Input, ListView, TabbedContent

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")  # verse 2
        await pilot.press("enter")
        await pilot.pause()

        tabs = app.screen.query_one(TabbedContent)
        tabs.active = "tab-dictionary"
        await pilot.pause()
        app.screen.query_one("#dict-filter", Input).focus()
        for ch in "love":
            await pilot.press(ch)
        await pilot.pause()

        dict_list = app.screen.query_one("#dict-list", ListView)
        assert len(dict_list.children) > 0
        assert "No matches" not in str(dict_list.children[0].children[0].content)


async def test_ctrl_t_opens_topics_and_running_one_shows_results(app):
    from bible_tui.ui.screens.topics import TopicsScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert isinstance(app.screen, TopicsScreen)

        await pilot.press("enter")  # first topic
        await pilot.pause()
        results = app.screen.query_one("#topic-results")
        assert results.display is True


async def test_choosing_a_topic_result_jumps_the_reader_there(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+t")
        await pilot.pause()
        await pilot.press("enter")  # first topic
        await pilot.pause()
        assert app.screen._results  # "Faith" has real matches in the shipped Bible text

        await pilot.press("enter")  # first result
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_capital_d_opens_display_settings_and_cycling_line_wrap_applies(app):
    from bible_tui.ui.screens.display_settings import DisplaySettingsScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        assert isinstance(app.screen, DisplaySettingsScreen)
        assert app.screen.config.line_wrap == "soft"

        await pilot.press("enter")  # cycle the first row, line wrap
        await pilot.pause()
        assert app.screen.config.line_wrap == "hard"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)
        assert app.config.line_wrap == "hard"
        assert app.screen.query_one(VerseView).has_class("wrap-none") is False


async def test_low_vision_mode_switches_to_a_high_contrast_theme(app):
    from bible_tui.ui.screens.display_settings import DisplaySettingsScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        for _ in range(2):  # line_wrap, verse_spacing, then low_vision
            await pilot.press("down")
        await pilot.press("enter")  # toggle low_vision on
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert app.config.low_vision is True
        assert app.theme in ("high-contrast", "daylight")
        assert app.screen.query_one(VerseView).has_class("low-vision-cursor")


async def test_hiding_the_chapter_heading_removes_it(app):
    from bible_tui.ui.screens.display_settings import DisplaySettingsScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        heading = app.screen.query_one("#chapter-heading")
        assert heading.display is True

        await pilot.press("D")
        await pilot.pause()
        for _ in range(3):  # line_wrap, verse_spacing, low_vision, chapter heading
            await pilot.press("down")
        await pilot.press("enter")  # toggle heading off
        await pilot.press("escape")
        await pilot.pause()

        assert heading.display is False


async def test_two_scripture_columns_splits_the_paragraph_view(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        for _ in range(4):  # line_wrap, spacing, low_vision, heading, columns
            await pilot.press("down")
        await pilot.press("enter")  # 1 -> 2 columns
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("p")  # switch to paragraph view
        await pilot.pause()

        from bible_tui.ui.widgets.paragraph_view import ParagraphView

        paragraph = app.screen.query_one(ParagraphView)
        assert paragraph.query_one("#paragraph-columns").display is True


async def test_ctrl_s_saves_the_current_search_by_name(app):
    from bible_tui.ui.screens.search import SearchScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        assert isinstance(app.screen, SearchScreen)
        for ch in "faith":
            await pilot.press(ch)
        await pilot.pause()

        await pilot.press("ctrl+s")
        await pilot.pause()
        for ch in "my search":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        saved = app.search.saved_searches()
        assert len(saved) == 1
        assert saved[0]["name"] == "my search"
        assert saved[0]["query"] == "faith"


async def test_ctrl_r_lists_saved_searches_above_recent_ones(app):
    from bible_tui.ui.screens.search import SearchScreen
    from bible_tui.services.search_service import SearchFilters

    async with app.run_test() as pilot:
        await pilot.pause()
        app.search.save_search("my faith search", "faith", SearchFilters())
        app.search.remember("grace")

        await pilot.press("slash")
        await pilot.pause()
        await pilot.press("ctrl+r")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, SearchScreen)
        assert screen._history == ["faith", "grace"]
        assert screen._saved_count == 1


async def test_choosing_a_saved_search_restores_it_and_runs_it(app):
    from bible_tui.services.search_service import SearchFilters

    async with app.run_test() as pilot:
        await pilot.pause()
        app.search.save_search("faith search", "faith", SearchFilters(testament="NT"))

        await pilot.press("slash")
        await pilot.pause()
        await pilot.press("ctrl+r")
        await pilot.pause()
        await pilot.press("enter")  # the one saved entry
        await pilot.pause()

        screen = app.screen
        from textual.widgets import Input

        assert screen.query_one("#search-input", Input).value == "faith"
        assert screen._results  # actually ran


async def test_g_opens_goto_and_jumps_to_the_reference(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("g")
        await pilot.pause()
        for ch in "John 3:16":
            await pilot.press(_key_for_char(ch))
        await pilot.press("enter")
        await pilot.pause()
        assert (screen.book_id, screen.chapter) == (43, 3)


async def test_question_mark_opens_help(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpModal)


# ----------------------------------------------------------------------
# Books-panel filtering
# ----------------------------------------------------------------------


async def test_tab_narrows_the_books_panel_to_the_old_testament(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        book_list = app.screen.query_one("#book-list", BookList)
        assert book_list.option_count == 66

        await pilot.press("tab")  # Whole Bible -> Old Testament
        await pilot.pause()
        assert book_list.option_count == 39
        assert book_list.border_subtitle == "Old Testament"


async def test_cycling_away_from_the_open_books_scope_does_not_navigate(app):
    # The default position is Genesis 1 - cycling to a scope that excludes
    # it (Gospels) must leave the reader exactly where it was. Narrowing
    # the sidebar list is a browsing aid, not a jump.
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        before = (screen.book_id, screen.chapter)

        for _ in range(8):  # Whole Bible -> ... -> Gospels
            await pilot.press("tab")
        await pilot.pause()

        assert (screen.book_id, screen.chapter) == before
        book_list = screen.query_one("#book-list", BookList)
        assert book_list.option_count == 4
        assert "not shown" in book_list.border_subtitle


async def test_cycling_to_a_scope_containing_the_open_book_keeps_it_highlighted(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        book_list = app.screen.query_one("#book-list", BookList)

        await pilot.press("tab")  # Old Testament - Genesis is still in it
        await pilot.pause()
        assert book_list.selected_book_id == app.screen.book_id
        assert book_list.border_subtitle == "Old Testament"


async def test_cycling_all_the_way_around_restores_every_book(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        book_list = app.screen.query_one("#book-list", BookList)

        for _ in range(12):  # a full lap back to Whole Bible
            await pilot.press("tab")
        await pilot.pause()

        assert book_list.option_count == 66
        assert book_list.selected_book_id == app.screen.book_id
        assert book_list.border_subtitle == "tab: filter"


async def test_shift_tab_cycles_backward(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        book_list = app.screen.query_one("#book-list", BookList)

        await pilot.press("shift+tab")  # Whole Bible -> Apocalyptic (wraps back)
        await pilot.pause()
        assert book_list.option_count == 1
        # Revelation-only scope, opened on Genesis - excluded, and said so.
        assert book_list.border_subtitle == "Apocalyptic - Genesis not shown"


async def test_the_reading_breadcrumb_shows_testament_and_category(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        scripture = app.screen.query_one("#scripture")
        assert scripture.border_title == "Genesis 1 · OT · Law"


# ----------------------------------------------------------------------
# Quit
# ----------------------------------------------------------------------


async def test_a_single_q_arms_the_quit_instead_of_exiting(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert app.is_running
        assert isinstance(app.screen, ReaderScreen)


async def test_qq_quits(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running


# ----------------------------------------------------------------------
# Session persistence
# ----------------------------------------------------------------------


async def test_session_state_is_saved_on_exit(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("t")  # theme -> midnight
        await pilot.press("p")  # view -> paragraph
        await pilot.pause()

    assert app.config.theme == "midnight"
    assert app.config.view_mode == VIEW_PARAGRAPH
    assert app.config.banner_shown is True


def _key_for_char(ch: str) -> str:
    return {" ": "space", ":": "colon"}.get(ch, ch)


async def test_the_verse_cursor_is_saved_and_restored(make_app):
    app = make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j", "j")  # cursor -> verse 3
        await pilot.pause()
    assert app.config.selected_verse == 3

    # A second launch reads that back out of the same tmp config.
    resumed = make_app()
    async with resumed.run_test() as pilot:
        await pilot.pause()
        assert resumed.screen.current_verse_number == 3


async def test_bracket_keys_move_between_chapters(app):
    # PageUp/PageDown stay with the focused list for scrolling within a
    # chapter, so chapter navigation gets the otherwise-unbound brackets.
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("right_square_bracket")
        await pilot.pause()
        assert (screen.book_id, screen.chapter) == (1, 2)
        await pilot.press("left_square_bracket")
        await pilot.pause()
        assert (screen.book_id, screen.chapter) == (1, 1)


async def test_chapter_navigation_rolls_over_into_the_next_book(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.jump(1, 50)  # Genesis 50, the last chapter
        await pilot.pause()
        await pilot.press("]")
        await pilot.pause()
        assert (screen.book_id, screen.chapter) == (2, 1)  # Exodus 1


# ----------------------------------------------------------------------
# Continuous reading and display toggles
# ----------------------------------------------------------------------


async def test_reading_past_the_last_verse_continues_into_the_next_chapter(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        verse_view = screen.query_one(VerseView)
        verse_view.index = len(verse_view.verses) - 1  # last verse of Genesis 1
        await pilot.pause()
        await pilot.press("j")
        await pilot.pause()
        assert (screen.book_id, screen.chapter) == (1, 2)
        assert screen.query_one(VerseView).index == 0


async def test_reading_back_past_the_first_verse_lands_on_the_previous_chapter_end(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.jump(1, 2)
        await pilot.pause()
        await pilot.press("k")
        await pilot.pause()
        verse_view = screen.query_one(VerseView)
        assert (screen.book_id, screen.chapter) == (1, 1)
        assert verse_view.index == len(verse_view.verses) - 1


async def test_a_pending_copy_range_is_not_broken_by_the_chapter_edge(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        verse_view = screen.query_one(VerseView)
        verse_view.index = len(verse_view.verses) - 1
        await pilot.press("Y")
        await pilot.pause()
        await pilot.press("j")
        await pilot.pause()
        # Still in Genesis 1 with the range intact, not carried into ch. 2.
        assert (screen.book_id, screen.chapter) == (1, 1)
        assert verse_view.has_range is True


async def test_f_toggles_focus_mode(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("f")
        await pilot.pause()
        assert screen.focus_mode is True
        assert screen.has_class("focus-mode")
        await pilot.press("f")
        await pilot.pause()
        assert screen.focus_mode is False


async def test_hash_toggles_verse_numbers(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("number_sign")
        await pilot.pause()
        assert screen.show_verse_numbers is False
        assert screen.has_class("hide-verse-numbers")


async def test_r_jumps_to_a_random_verse(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        start = (screen.book_id, screen.chapter)
        # Genesis 1 is one chapter out of 1,189; a random jump landing back
        # on it twice running would be a one-in-a-million coincidence.
        await pilot.press("r")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert (screen.book_id, screen.chapter) != start


async def test_backslash_opens_the_translation_comparison(app):
    from bible_tui.ui.screens.compare import CompareScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("backslash")
        await pilot.pause()
        assert isinstance(app.screen, CompareScreen)
        assert app.screen.reference == "Genesis 1:1"


async def test_returning_to_a_book_resumes_where_you_left_it(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.jump(43, 12)  # read John 12
        await pilot.pause()
        screen.jump(1, 1)  # go back to Genesis
        await pilot.pause()
        # Moving the Books cursor onto John should preview John 12, not John 1.
        screen.query_one("#book-list", BookList).select_book_id(43)
        await pilot.pause(0.3)
        assert (screen.book_id, screen.chapter) == (43, 12)


# ----------------------------------------------------------------------
# Reading record
# ----------------------------------------------------------------------


async def test_capital_s_opens_the_reading_record(app):
    from bible_tui.ui.screens.stats import StatsScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("S")
        await pilot.pause()
        assert isinstance(app.screen, StatsScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_a_fresh_record_says_so_rather_than_showing_zeroes(app):
    from textual.widgets import Static

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("S")
        await pilot.pause()
        empty = app.screen.query_one("#stats-empty", Static)
        assert empty.display is True
        assert app.screen.query_one("#stats-overall", Static).display is False


async def test_lingering_on_a_chapter_earns_it_a_place_in_the_record(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        # Standing in for a real minute spent reading - the clock is the one
        # thing a Pilot test can't wait out.
        screen._chapter_seconds += 120
        screen.jump(43, 3)
        await pilot.pause()

        totals = app.stats.totals()
        assert totals.chapters == 1
        assert totals.seconds >= 120


async def test_flipping_through_chapters_earns_nothing(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        for _ in range(4):
            await pilot.press("right_square_bracket")
            await pilot.pause()
        assert app.stats.totals().chapters == 0


async def test_the_record_reflects_reading_done_this_session(app):
    from textual.widgets import Static

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._chapter_seconds += 120
        screen.jump(43, 3)
        await pilot.pause()

        await pilot.press("S")
        await pilot.pause()
        assert app.screen.query_one("#stats-empty", Static).display is False
        assert "Chapters read" in str(app.screen.query_one("#stats-overall", Static).visual)


async def test_the_whole_book_list_is_reachable_by_scrolling(app):
    from textual.containers import VerticalScroll

    # #stats-body is a Vertical, which is height:1fr by default - left that
    # way, everything past the first screenful is clipped rather than
    # scrollable, and the per-book progress can never be seen.
    async with app.run_test(size=(96, 30)) as pilot:
        await pilot.pause()
        app.stats.record(1, 1, "KJV", seconds=300, verses=31)
        await pilot.press("S")
        await pilot.pause()
        scroll = app.screen.query_one(VerticalScroll)
        assert scroll.max_scroll_y > 0

        scroll.scroll_end(animate=False)
        await pilot.pause()
        rendered = "\n".join(
            "".join(seg.text for seg in strip)
            for strip in app.screen._compositor.render_strips()
        )
        assert "Revelation" in rendered


async def test_time_in_a_modal_is_not_counted_as_reading(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("slash")  # open search
        await pilot.pause()
        assert screen._chapter_opened_at is None  # clock stopped
        await pilot.press("escape")
        await pilot.pause()
        assert screen._chapter_opened_at is not None  # and started again


async def test_reading_either_side_of_a_modal_is_one_visit(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._chapter_seconds += 60
        await pilot.press("question_mark")  # help, then back
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        screen._chapter_seconds += 60

        screen.jump(43, 3)
        await pilot.pause()
        totals = app.stats.totals()
        assert totals.chapters == 1  # one visit, not two
        assert totals.seconds >= 120


# ----------------------------------------------------------------------
# Bookmarks
# ----------------------------------------------------------------------


async def test_capital_b_prompts_for_a_label_and_saves_it(app):
    from bible_tui.ui.screens.prompt import PromptModal

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("B")
        await pilot.pause()
        assert isinstance(app.screen, PromptModal)

        await pilot.press("f", "o", "r", " ", "s", "u", "n", "d", "a", "y")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)
        assert app.annotations.bookmark_label(1, 1, 1) == "for sunday"
        assert app.annotations.is_bookmarked(1, 1, 1)


async def test_cancelling_the_label_prompt_changes_nothing(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("B")
        await pilot.pause()
        await pilot.press("x", "escape")
        await pilot.pause()
        assert app.annotations.is_bookmarked(1, 1, 1) is False


async def test_the_bookmark_list_filters_as_you_type(app):
    from textual.widgets import Input, ListView

    async with app.run_test() as pilot:
        await pilot.pause()
        app.annotations.label_bookmark(43, 3, 16, "answered prayer")
        app.annotations.toggle_bookmark(1, 1, 1)

        await pilot.press("ctrl+b")
        await pilot.pause()
        screen = app.screen
        assert len(screen.query_one("#bookmarks-list", ListView).children) == 2

        screen.query_one("#bookmarks-filter", Input).value = "answered"
        await pilot.pause()
        assert len(screen._bookmarks) == 1
        assert screen._bookmarks[0]["book_name"] == "John"


async def test_o_reorders_the_bookmark_list(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        app.annotations.toggle_bookmark(66, 22, 21)
        app.annotations.toggle_bookmark(1, 1, 1)

        await pilot.press("ctrl+b")
        await pilot.pause()
        screen = app.screen
        assert screen._bookmarks[0]["book_name"] == "Genesis"  # newest first

        await pilot.press("o")
        await pilot.pause()
        assert [b["book_name"] for b in screen._bookmarks] == ["Genesis", "Revelation"]


async def test_d_deletes_the_selected_bookmark(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        app.annotations.toggle_bookmark(43, 3, 16)
        app.annotations.toggle_bookmark(1, 1, 1)

        await pilot.press("ctrl+b")
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert len(app.annotations.list_bookmarks()) == 1
        assert len(app.screen._bookmarks) == 1


async def test_choosing_a_bookmark_jumps_the_reader_there(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        app.annotations.toggle_bookmark(43, 3, 16)

        await pilot.press("ctrl+b")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)
        assert (app.screen.book_id, app.screen.chapter) == (43, 3)


# ----------------------------------------------------------------------
# Favourites, folders, tags, reading lists
# ----------------------------------------------------------------------


async def test_star_toggles_a_favourite(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("*")
        await pilot.pause()
        assert app.annotations.is_favourite(1, 1, 1) is True
        await pilot.press("*")
        await pilot.pause()
        assert app.annotations.is_favourite(1, 1, 1) is False


async def test_v_switches_the_bookmarks_browser_to_favourites(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        app.annotations.toggle_bookmark(1, 1, 1)
        app.annotations.toggle_favourite(43, 3, 16)

        await pilot.press("ctrl+b")
        await pilot.pause()
        screen = app.screen
        assert [b["book_name"] for b in screen._bookmarks] == ["Genesis"]

        await pilot.press("v")
        await pilot.pause()
        assert [b["book_name"] for b in screen._bookmarks] == ["John"]


async def test_f_files_a_bookmark_into_a_new_folder(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        app.annotations.toggle_bookmark(1, 1, 1)

        await pilot.press("ctrl+b")
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        await pilot.press("s", "u", "n", "d", "a", "y")
        await pilot.press("enter")
        await pilot.pause()
        rows = app.annotations.list_bookmarks()
        assert rows[0]["folder_name"] == "sunday"


async def test_t_tags_a_bookmark(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        app.annotations.toggle_bookmark(1, 1, 1)

        await pilot.press("ctrl+b")
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        await pilot.press("f", "a", "i", "t", "h")
        await pilot.press("enter")
        await pilot.pause()
        assert app.annotations.tags_for_verse(1, 1, 1) == ["faith"]


async def test_capital_l_adds_the_selected_verse_to_a_new_reading_list(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("L")
        await pilot.pause()
        await pilot.press("a", "d", "v", "e", "n", "t")
        await pilot.press("enter")
        await pilot.pause()

        lists = app.reading_lists.list_lists()
        assert [r["name"] for r in lists] == ["advent"]
        items = app.reading_lists.items(lists[0]["id"])
        assert (items[0]["chapter"], items[0]["verse"]) == (1, 1)


async def test_ctrl_l_from_bookmarks_opens_reading_lists(app):
    from bible_tui.ui.screens.reading_lists import ReadingListsScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        app.reading_lists.create_list("Advent")

        await pilot.press("ctrl+b")
        await pilot.pause()
        await pilot.press("ctrl+l")
        await pilot.pause()
        assert isinstance(app.screen, ReadingListsScreen)
        assert [r["name"] for r in app.screen._lists] == ["Advent"]


async def test_selecting_a_reading_list_item_jumps_the_reader_there(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        list_id = app.reading_lists.create_list("Advent")
        app.reading_lists.add_verse(list_id, 43, 3, 16)

        await pilot.press("ctrl+b")
        await pilot.pause()
        await pilot.press("ctrl+l")
        await pilot.pause()
        await pilot.press("enter")  # open the one list
        await pilot.pause()
        await pilot.press("enter")  # select the one item
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)
        assert (app.screen.book_id, app.screen.chapter) == (43, 3)


# ----------------------------------------------------------------------
# Reading plans
# ----------------------------------------------------------------------


async def test_the_catalogue_is_what_you_see_with_no_plan(app):
    from textual.widgets import ListView

    from bible_tui.services.plan_service import PLAN_KINDS
    from bible_tui.ui.screens.plans import PlansScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("P")
        await pilot.pause()
        assert isinstance(app.screen, PlansScreen)
        assert len(app.screen.query_one("#plan-entries", ListView).children) == len(PLAN_KINDS)


async def test_choosing_a_plan_starts_it_and_shows_today(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("P")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        plan = app.plans.active_plan()
        assert plan is not None and plan["plan_type"] == "one_year"
        assert app.screen._entries  # today's reading, not the catalogue


async def test_choosing_todays_reading_jumps_there_and_marks_it_done(app):
    from datetime import date

    async with app.run_test() as pilot:
        await pilot.pause()
        plan_id = app.plans.create_plan("gospels_40", date.today())

        await pilot.press("P")
        await pilot.pause()
        first = app.screen._entries[0]
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ReaderScreen)
        assert app.screen.book_id == first["book_id"]
        assert app.plans.progress(plan_id)[0] == 1


async def test_being_behind_on_a_plan_shows_a_reminder_toast(app):
    from datetime import date, timedelta

    async with app.run_test() as pilot:
        await pilot.pause()
        app.plans.create_plan("gospels_40", date.today() - timedelta(days=4))

        warned = []
        app.notify = lambda *a, **k: warned.append(a[0] if a else "")
        app._remind_if_behind_on_plan()

        assert len(warned) == 1
        assert "behind" in warned[0]


async def test_being_current_on_a_plan_shows_no_reminder(app):
    from datetime import date

    async with app.run_test() as pilot:
        await pilot.pause()
        app.plans.create_plan("gospels_40", date.today())

        warned = []
        app.notify = lambda *a, **k: warned.append(a[0] if a else "")
        app._remind_if_behind_on_plan()

        assert warned == []


async def test_no_active_plan_shows_no_reminder(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        warned = []
        app.notify = lambda *a, **k: warned.append(a[0] if a else "")
        app._remind_if_behind_on_plan()
        assert warned == []


async def test_the_catch_up_view_lists_what_you_missed(app):
    from datetime import date, timedelta

    async with app.run_test() as pilot:
        await pilot.pause()
        app.plans.create_plan("gospels_40", date.today() - timedelta(days=4))

        await pilot.press("P")
        await pilot.pause()
        today_count = len(app.screen._entries)

        await pilot.press("c")
        await pilot.pause()
        assert app.screen.showing_catch_up
        assert len(app.screen._entries) > today_count


async def test_abandoning_a_plan_returns_you_to_the_catalogue(app):
    from datetime import date

    async with app.run_test() as pilot:
        await pilot.pause()
        app.plans.create_plan("gospels_40", date.today())

        await pilot.press("P")
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        assert app.plans.list_plans() == []
        assert app.screen.mode == "catalogue"


async def test_switching_rotates_between_started_plans(app):
    from datetime import date

    async with app.run_test() as pilot:
        await pilot.pause()
        first = app.plans.create_plan("gospels_40", date.today())
        second = app.plans.create_plan("nt_90", date.today())

        await pilot.press("P")
        await pilot.pause()
        assert app.plans.active_plan()["id"] == second

        await pilot.press("s")
        await pilot.pause()
        assert app.plans.active_plan()["id"] == first


async def test_a_damaged_database_is_reported_rather_than_hiding_the_app(app, monkeypatch):
    from bible_tui.services.backup_service import IntegrityReport

    monkeypatch.setattr(
        "bible_tui.services.backup_service.BackupService.check",
        lambda self, thorough=False: IntegrityReport(False, ("page 7 is malformed",)),
    )
    warned: list[str] = []
    async with app.run_test() as pilot:
        await pilot.pause()
        monkeypatch.setattr(app, "notify", lambda *a, **k: warned.append(a[0] if a else ""))
        await app.run_worker(app._warn_if_damaged, thread=True).wait()
        await pilot.pause()

        assert any("problem" in message for message in warned)
        # And the reader still opens - a partly-readable database beats none.
        assert isinstance(app.screen, ReaderScreen)


async def test_a_healthy_database_says_nothing_on_launch(app):
    warned: list[str] = []
    async with app.run_test() as pilot:
        await pilot.pause()
        app.notify = lambda *a, **k: warned.append(a[0] if a else "")
        await app.run_worker(app._warn_if_damaged, thread=True).wait()
        await pilot.pause()
        assert warned == []


# ----------------------------------------------------------------------
# Reading modes
# ----------------------------------------------------------------------


async def test_capital_r_opens_the_reading_modes_picker(app):
    from bible_tui.ui.screens.reading_modes import ReadingModesScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        assert isinstance(app.screen, ReadingModesScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_choosing_memorise_opens_the_drill_on_the_selected_verse(app):
    from textual.widgets import Static

    from bible_tui.ui.screens.memorise import MemoriseScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        await pilot.press("enter")  # first item in the picker: Memorise
        await pilot.pause()
        assert isinstance(app.screen, MemoriseScreen)

        # Space hides more of the verse, without touching the surrounding
        # punctuation or the reference line.
        before = str(app.screen.query_one("#verse-text", Static).visual)
        await pilot.press("space")
        await pilot.pause()
        after = str(app.screen.query_one("#verse-text", Static).visual)
        assert before != after

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_choosing_speed_read_streams_the_chapters_words(app):
    from bible_tui.ui.screens.speed_read import SpeedReadScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        await pilot.press("down", "down", "down", "enter")  # 4th item: Speed-read
        await pilot.pause()
        assert isinstance(app.screen, SpeedReadScreen)
        assert app.screen.words  # Genesis 1 has words to stream
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_read_aloud_is_reported_unavailable_off_macos(app, monkeypatch):
    from bible_tui.ui.widgets.status_bar import StatusBar

    monkeypatch.setattr(
        "bible_tui.ui.screens.reader.tts_service.is_available", lambda: False
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        await pilot.press("down", "down", "down", "down", "enter")  # 5th item: Read aloud
        await pilot.pause()
        # No backend on this platform - back in the reader with a status
        # message, not stuck waiting on a process that will never start.
        assert isinstance(app.screen, ReaderScreen)
        assert "macOS" in str(app.screen.query_one(StatusBar).visual)


async def _open_mode(pilot, downs: int):
    await pilot.press("R")
    await pilot.pause()
    for _ in range(downs):
        await pilot.press("down")
    await pilot.press("enter")
    await pilot.pause()


async def test_choosing_sermon_opens_the_chapter_one_verse_at_a_time(app):
    from bible_tui.ui.screens.sermon import SermonScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await _open_mode(pilot, 5)  # 6th item: Sermon
        assert isinstance(app.screen, SermonScreen)
        assert app.screen.slides  # Genesis 1 has verses to present

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_choosing_contemplative_opens_the_selected_verse_with_a_timer(app):
    from bible_tui.ui.screens.contemplative import ContemplativeScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await _open_mode(pilot, 6)  # 7th item: Contemplative
        assert isinstance(app.screen, ContemplativeScreen)
        assert app.screen.remaining == 90

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_choosing_meditative_toggles_auto_scroll_on_and_off(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await _open_mode(pilot, 7)  # 8th item: Meditative
        assert isinstance(screen, ReaderScreen)  # a toggle, not a new screen
        assert screen._meditative_timer is not None

        await _open_mode(pilot, 7)  # toggled again: stops
        assert screen._meditative_timer is None


async def test_choosing_prayer_opens_guided_prompts_on_the_selected_verse(app):
    from bible_tui.ui.screens.prayer import PrayerScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await _open_mode(pilot, 8)  # 9th item: Prayer
        assert isinstance(app.screen, PrayerScreen)
        assert app.screen.reference == "Genesis 1:1"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_finishing_a_prayer_session_adds_a_new_note_each_time(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        for _ in range(2):  # praying over the same verse twice...
            await _open_mode(pilot, 8)
            await pilot.press("A", "d", "o", "r", "e", "d")
            await pilot.press("ctrl+s")
            await pilot.pause()

        notes = app.screen.annotations.get_notes(1, 1, 1)
        assert len(notes) == 2  # ...leaves two notes behind, not one overwritten


async def test_choosing_journal_opens_a_full_screen_editor_on_the_selected_verse(app):
    from bible_tui.ui.screens.journal import JournalScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await _open_mode(pilot, 9)  # 10th item: Journal
        assert isinstance(app.screen, JournalScreen)
        assert app.screen.reference == "Genesis 1:1"

        await pilot.press("i", "n", " ", "t", "h", "e", " ", "b", "e", "g", "i", "n", "n", "i", "n", "g")
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)
        assert app.screen.annotations.get_notes(1, 1, 1)[0]["body"] == "in the beginning"


async def test_choosing_academic_shows_interlinear_commentary_and_xrefs(app):
    from bible_tui.ui.screens.academic import AcademicScreen

    async with app.run_test() as pilot:
        await pilot.pause()
        await _open_mode(pilot, 10)  # 11th item: Academic
        assert isinstance(app.screen, AcademicScreen)
        assert app.screen.verse.reference == "Genesis 1:1"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ReaderScreen)


async def test_ctrl_p_toggles_a_markdown_preview_in_the_note_editor(app):
    from textual.widgets import Markdown, TextArea

    from bible_tui.ui.screens.note import NoteModal

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, NoteModal)
        area = app.screen.query_one("#note-area", TextArea)
        preview = app.screen.query_one("#note-preview", Markdown)
        assert area.display is True
        assert preview.display is False

        await pilot.press("*", "*", "b", "o", "l", "d", "*", "*")
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert area.display is False
        assert preview.display is True

        await pilot.press("ctrl+p")
        await pilot.pause()
        assert area.display is True
        assert preview.display is False
        assert area.text == "**bold**"


async def test_ctrl_p_toggles_a_markdown_preview_in_the_journal(app):
    from textual.widgets import Markdown, TextArea

    async with app.run_test() as pilot:
        await pilot.pause()
        await _open_mode(pilot, 9)  # 10th item: Journal
        area = app.screen.query_one("#journal-area", TextArea)
        preview = app.screen.query_one("#journal-preview", Markdown)
        assert area.display is True
        assert preview.display is False

        await pilot.press("ctrl+p")
        await pilot.pause()
        assert area.display is False
        assert preview.display is True
