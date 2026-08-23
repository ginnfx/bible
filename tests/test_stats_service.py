"""Reading statistics.

Every test pins ``today`` and the recording timestamps explicitly. Streaks
and calendars are the kind of thing that pass in the morning and fail at
midnight, and a suite that depends on the wall clock is worse than none.
"""

from __future__ import annotations

import datetime as dt

import pytest

from bible_tui.services.stats_service import MINIMUM_SECONDS, StatsService

TODAY = dt.date(2026, 3, 15)


@pytest.fixture
def stats(conn):
    return StatsService(conn)


def _read(stats: StatsService, day: dt.date, book_id: int = 1, chapter: int = 1, **kwargs) -> bool:
    return stats.record(
        book_id,
        chapter,
        "KJV",
        seconds=kwargs.pop("seconds", 120),
        verses=kwargs.pop("verses", 31),
        when=dt.datetime.combine(day, dt.time(9, 0)),
    )


# ----------------------------------------------------------------------
# Recording
# ----------------------------------------------------------------------


def test_a_read_chapter_is_recorded(stats):
    assert _read(stats, TODAY) is True
    assert stats.totals().chapters == 1


def test_flipping_past_a_chapter_does_not_count(stats):
    assert _read(stats, TODAY, seconds=MINIMUM_SECONDS - 1) is False
    assert stats.totals().chapters == 0


def test_the_threshold_itself_counts(stats):
    assert _read(stats, TODAY, seconds=MINIMUM_SECONDS) is True


def test_everything_can_be_forgotten(stats):
    _read(stats, TODAY)
    stats.forget_everything()
    assert stats.totals().chapters == 0


# ----------------------------------------------------------------------
# Totals
# ----------------------------------------------------------------------


def test_totals_on_an_empty_history_are_zero_not_none(stats):
    totals = stats.totals()
    assert (totals.chapters, totals.verses, totals.seconds, totals.days) == (0, 0, 0, 0)
    assert totals.first_day is None
    assert totals.average_seconds_per_chapter == 0


def test_rereading_a_chapter_counts_once_towards_unique(stats):
    _read(stats, TODAY, chapter=1)
    _read(stats, TODAY - dt.timedelta(days=1), chapter=1)
    _read(stats, TODAY, chapter=2)
    totals = stats.totals()
    assert totals.chapters == 3
    assert totals.unique_chapters == 2


def test_totals_sum_time_and_verses(stats):
    _read(stats, TODAY, seconds=100, verses=10)
    _read(stats, TODAY, chapter=2, seconds=200, verses=20)
    totals = stats.totals()
    assert totals.seconds == 300 and totals.verses == 30
    assert totals.average_seconds_per_chapter == 150


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(45, "45s"), (60, "1m"), (900, "15m"), (3600, "1h 0m"), (7860, "2h 11m")],
)
def test_time_reads_the_way_a_person_would_say_it(stats, seconds, expected):
    _read(stats, TODAY, seconds=seconds)
    assert stats.totals().describe_time() == expected


# ----------------------------------------------------------------------
# Streaks
# ----------------------------------------------------------------------


def test_no_reading_means_no_streak(stats):
    streak = stats.streak(TODAY)
    assert (streak.current, streak.longest) == (0, 0)
    assert "No streak yet" in streak.describe()


def test_consecutive_days_build_a_streak(stats):
    for offset in range(3):
        _read(stats, TODAY - dt.timedelta(days=offset))
    streak = stats.streak(TODAY)
    assert streak.current == 3 and streak.longest == 3
    assert streak.read_today is True
    assert streak.describe() == "3 days"


def test_yesterday_still_holds_the_streak_open(stats):
    # Reporting a streak broken before the day is over would be a lie that
    # discourages the person who is about to read tonight.
    _read(stats, TODAY - dt.timedelta(days=2))
    _read(stats, TODAY - dt.timedelta(days=1))
    streak = stats.streak(TODAY)
    assert streak.current == 2 and streak.read_today is False
    assert "keep it" in streak.describe()


def test_a_missed_day_ends_the_streak_but_not_the_record(stats):
    for offset in (5, 4, 3):
        _read(stats, TODAY - dt.timedelta(days=offset))
    streak = stats.streak(TODAY)
    assert streak.current == 0
    assert streak.longest == 3


def test_the_longest_streak_survives_a_later_shorter_one(stats):
    for offset in (10, 9, 8, 7):
        _read(stats, TODAY - dt.timedelta(days=offset))
    _read(stats, TODAY)
    streak = stats.streak(TODAY)
    assert streak.current == 1 and streak.longest == 4


def test_several_chapters_in_one_day_are_still_one_day(stats):
    for chapter in (1, 2, 3):
        _read(stats, TODAY, chapter=chapter)
    assert stats.streak(TODAY).current == 1


def test_one_day_reads_as_singular(stats):
    _read(stats, TODAY)
    assert stats.streak(TODAY).describe() == "1 day"


# ----------------------------------------------------------------------
# Coverage
# ----------------------------------------------------------------------


def test_coverage_lists_every_book_even_unread_ones(stats):
    coverage = stats.coverage()
    assert len(coverage.books) == 66
    assert coverage.chapters_read == 0
    assert coverage.percent == 0.0


def test_reading_moves_a_book_forward(stats):
    _read(stats, TODAY, book_id=43, chapter=3)
    john = next(b for b in stats.coverage().books if b.name == "John")
    assert john.chapters_read == 1
    assert john.chapter_count == 21
    assert john.percent == 5
    assert not john.is_complete


def test_a_book_is_complete_once_every_chapter_is_read(stats):
    _read(stats, TODAY, book_id=65, chapter=1)  # Jude is a single chapter
    jude = next(b for b in stats.coverage().books if b.name == "Jude")
    assert jude.is_complete
    assert stats.coverage().books_complete == 1


def test_rereading_does_not_inflate_coverage(stats):
    for _ in range(4):
        _read(stats, TODAY, book_id=43, chapter=3)
    john = next(b for b in stats.coverage().books if b.name == "John")
    assert john.chapters_read == 1


def test_coverage_splits_by_testament(stats):
    _read(stats, TODAY, book_id=1, chapter=1)
    coverage = stats.coverage()
    assert coverage.testament("OT").chapters_read == 1
    assert coverage.testament("NT").chapters_read == 0
    assert coverage.testament("NT").chapters_total > 0


def test_books_started_counts_partial_books(stats):
    _read(stats, TODAY, book_id=1, chapter=1)
    coverage = stats.coverage()
    assert coverage.books_started == 1 and coverage.books_complete == 0


# ----------------------------------------------------------------------
# Charts and history
# ----------------------------------------------------------------------


def test_most_read_ranks_books(stats):
    for chapter in (1, 2, 3):
        _read(stats, TODAY, book_id=19, chapter=chapter)
    _read(stats, TODAY, book_id=43, chapter=1)
    assert stats.most_read(2) == [("Psalms", 3), ("John", 1)]


def test_daily_activity_fills_in_the_quiet_days(stats):
    _read(stats, TODAY)
    _read(stats, TODAY - dt.timedelta(days=2))
    activity = stats.daily_activity(days=3, today=TODAY)
    assert [count for _, count in activity] == [1, 0, 1]
    assert [day for day, _ in activity][-1] == TODAY


def test_daily_activity_ignores_older_reading(stats):
    _read(stats, TODAY - dt.timedelta(days=40))
    assert sum(count for _, count in stats.daily_activity(days=7, today=TODAY)) == 0


def test_history_is_newest_first(stats):
    _read(stats, TODAY, book_id=1, chapter=1)
    _read(stats, TODAY, book_id=43, chapter=3)
    rows = stats.history()
    assert rows[0]["book_name"] == "John" and rows[0]["chapter"] == 3


# ----------------------------------------------------------------------
# Pace
# ----------------------------------------------------------------------


def test_pace_is_honest_about_having_nothing_to_go_on(stats):
    assert "Not enough" in stats.pace()


def test_pace_estimates_from_the_rate_so_far(stats):
    for offset in range(10):
        for chapter in range(1, 6):
            _read(stats, TODAY - dt.timedelta(days=offset), book_id=19, chapter=chapter + offset * 5)
    assert "to finish at this pace" in stats.pace()


def test_a_malformed_date_does_not_break_the_streak(stats, conn):
    conn.execute(
        """
        INSERT INTO reading_events
            (book_id, chapter, translation_code, read_on, started_at, seconds, verses)
        VALUES (1, 1, 'KJV', 'sometime', 'sometime', 60, 1)
        """
    )
    conn.commit()
    _read(stats, TODAY)
    assert stats.streak(TODAY).current == 1


def test_a_broken_streak_does_not_pretend_you_never_read(stats):
    for offset in (9, 8, 7):
        _read(stats, TODAY - dt.timedelta(days=offset))
    described = stats.streak(TODAY).describe()
    assert "No streak yet" not in described
    assert "Broken" in described


# ----------------------------------------------------------------------
# Word-level stats
# ----------------------------------------------------------------------


def test_unread_chapters_contribute_no_vocabulary(stats):
    assert stats.unique_vocabulary_count() == 0
    assert stats.word_frequency() == []


def test_reading_a_chapter_builds_its_vocabulary(stats):
    _read(stats, TODAY, book_id=1, chapter=1)  # Genesis 1: three seeded verses
    assert stats.unique_vocabulary_count() > 0
    assert ("god", 2) in stats.word_frequency(limit=50) or any(
        word == "god" for word, _ in stats.word_frequency(limit=50)
    )


def test_rereading_a_chapter_does_not_inflate_vocabulary(stats):
    _read(stats, TODAY, book_id=1, chapter=1)
    once = stats.unique_vocabulary_count()
    _read(stats, TODAY - dt.timedelta(days=1), book_id=1, chapter=1)
    assert stats.unique_vocabulary_count() == once


def test_word_frequency_is_ranked_most_common_first(stats):
    _read(stats, TODAY, book_id=1, chapter=1)
    freq = stats.word_frequency(limit=5)
    counts = [n for _, n in freq]
    assert counts == sorted(counts, reverse=True)


def test_words_per_minute_is_zero_with_no_reading(stats):
    assert stats.words_per_minute() == 0.0


def test_words_per_minute_is_positive_after_reading(stats):
    _read(stats, TODAY, book_id=1, chapter=1, seconds=60)
    assert stats.words_per_minute() > 0


def test_rereading_a_chapter_counts_its_words_again_for_wpm(stats):
    _read(stats, TODAY, book_id=1, chapter=1, seconds=60)
    once = stats.words_per_minute()
    _read(stats, TODAY - dt.timedelta(days=1), book_id=1, chapter=1, seconds=60)
    twice = stats.words_per_minute()
    # Same words-per-event, same minutes-per-event -> the rate is unchanged,
    # even though total words counted (unlike vocabulary) doubled.
    assert twice == pytest.approx(once, rel=0.01)


def test_verse_length_stats_finds_the_extremes(stats):
    shortest, longest, average = stats.verse_length_stats("KJV")
    assert shortest.words <= average <= longest.words
    assert shortest.reference
    assert longest.reference


def test_verse_length_stats_on_an_unknown_translation_is_empty(stats):
    shortest, longest, average = stats.verse_length_stats("XYZ")
    assert shortest.words == 0
    assert average == 0.0


# ----------------------------------------------------------------------
# Weekly summary
# ----------------------------------------------------------------------


def test_weekly_activity_is_zero_filled_and_ordered_oldest_first(stats):
    weeks = stats.weekly_activity(weeks=4, today=TODAY)
    assert len(weeks) == 4
    assert weeks[-1][0] <= TODAY
    assert all(n >= 0 for _, n in weeks)


def test_weekly_activity_counts_reads_in_the_right_week(stats):
    _read(stats, TODAY)
    weeks = stats.weekly_activity(weeks=2, today=TODAY)
    assert weeks[-1][1] == 1


# ----------------------------------------------------------------------
# Milestones
# ----------------------------------------------------------------------


def test_crossing_a_streak_milestone_is_reported(stats):
    for offset in range(6, -1, -1):  # 7 consecutive days ending today
        before_coverage = stats.coverage()
        before_streak = stats.streak(TODAY - dt.timedelta(days=offset))
        _read(stats, TODAY - dt.timedelta(days=offset))
    messages = stats.check_milestones(before_coverage, before_streak, today=TODAY)
    assert any("7-day" in m for m in messages)


def test_no_milestone_fires_when_nothing_was_crossed(stats):
    _read(stats, TODAY)
    before_coverage = stats.coverage()
    before_streak = stats.streak(TODAY)
    _read(stats, TODAY, chapter=2)
    assert stats.check_milestones(before_coverage, before_streak, today=TODAY) == []


def test_completing_a_book_is_reported(stats, conn):
    # Genesis is seeded with chapters 1, 2 and 50 in this fixture's
    # verses table; chapter_count for Genesis (book_id 1) is whatever
    # CANONICAL_BOOKS says, so drive completion through a book with a
    # small, controllable chapter_count instead: patch it down to 1.
    conn.execute("UPDATE books SET chapter_count = 1 WHERE id = 1")
    conn.commit()
    before_coverage = stats.coverage()
    before_streak = stats.streak(TODAY)
    _read(stats, TODAY, book_id=1, chapter=1)
    messages = stats.check_milestones(before_coverage, before_streak, today=TODAY)
    assert any("complete" in m for m in messages)


# ----------------------------------------------------------------------
# Reading goals
# ----------------------------------------------------------------------


def test_no_goal_means_no_progress(stats):
    assert stats.get_goal() is None
    assert stats.goal_progress_today() is None


def test_setting_a_chapter_goal_tracks_todays_progress(stats):
    stats.set_goal("chapters", 3)
    _read(stats, TODAY)
    progress, target, kind = stats.goal_progress_today(today=TODAY)
    assert (progress, target, kind) == (1, 3, "chapters")


def test_setting_a_minutes_goal_tracks_todays_progress(stats):
    stats.set_goal("minutes", 10)
    _read(stats, TODAY, seconds=120)
    progress, target, kind = stats.goal_progress_today(today=TODAY)
    assert target == 10 and kind == "minutes" and progress == 2


def test_clearing_a_goal_removes_it(stats):
    stats.set_goal("chapters", 3)
    stats.clear_goal()
    assert stats.get_goal() is None
