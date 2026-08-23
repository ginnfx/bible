from datetime import date, timedelta

from bible_tui.services.plan_service import PlanService, _merge_consecutive_chapters


def test_merge_consecutive_chapters_within_one_book():
    chapters = [(1, 1), (1, 2), (1, 3)]
    assert _merge_consecutive_chapters(chapters) == [(1, 1, 3)]


def test_merge_consecutive_chapters_across_books():
    chapters = [(1, 49), (1, 50), (2, 1)]
    assert _merge_consecutive_chapters(chapters) == [(1, 49, 50), (2, 1, 1)]


def test_merge_consecutive_chapters_empty():
    assert _merge_consecutive_chapters([]) == []


def test_create_one_year_plan_covers_every_chapter(conn):
    plan_service = PlanService(conn)
    plan_id = plan_service.create_one_year_plan(date(2026, 1, 1))

    total_chapters_in_plan = 0
    rows = conn.execute(
        "SELECT chapter_start, chapter_end FROM plan_entries WHERE plan_id = ?", (plan_id,)
    ).fetchall()
    for r in rows:
        total_chapters_in_plan += r["chapter_end"] - r["chapter_start"] + 1

    total_chapters_in_bible = sum(b["chapter_count"] for b in conn.execute("SELECT chapter_count FROM books"))
    assert total_chapters_in_plan == total_chapters_in_bible


def test_create_one_year_plan_interleaves_ot_and_nt_early_on(conn):
    plan_service = PlanService(conn)
    plan_id = plan_service.create_one_year_plan(date(2026, 1, 1))
    day_one = plan_service.entries_for_day(plan_id, 1)
    testaments = {
        conn.execute("SELECT testament FROM books WHERE id = ?", (e["book_id"],)).fetchone()["testament"]
        for e in day_one
    }
    assert testaments == {"OT", "NT"}


def test_mark_complete_and_progress(conn):
    plan_service = PlanService(conn)
    plan_id = plan_service.create_one_year_plan(date.today())
    day_one = plan_service.entries_for_day(plan_id, 1)

    completed, total = plan_service.progress(plan_id)
    assert completed == 0

    for entry in day_one:
        plan_service.mark_complete(entry["id"])

    completed, total = plan_service.progress(plan_id)
    assert completed == 1


def test_current_streak_counts_consecutive_completed_days(conn):
    plan_service = PlanService(conn)
    start = date.today() - timedelta(days=2)
    plan_id = plan_service.create_one_year_plan(start)

    # Complete day 1 and day 2 (today is day 3) but leave day 3 undone.
    for day in (1, 2):
        for entry in plan_service.entries_for_day(plan_id, day):
            plan_service.mark_complete(entry["id"])

    assert plan_service.current_streak(plan_id) == 0  # today's entries aren't done yet

    for entry in plan_service.entries_for_day(plan_id, 3):
        plan_service.mark_complete(entry["id"])

    assert plan_service.current_streak(plan_id) == 3


def test_current_streak_breaks_on_gap(conn):
    plan_service = PlanService(conn)
    start = date.today() - timedelta(days=3)
    plan_id = plan_service.create_one_year_plan(start)

    # Complete day 1 and today (day 4), but skip days 2-3.
    for entry in plan_service.entries_for_day(plan_id, 1):
        plan_service.mark_complete(entry["id"])
    for entry in plan_service.entries_for_day(plan_id, 4):
        plan_service.mark_complete(entry["id"])

    assert plan_service.current_streak(plan_id) == 1


# ----------------------------------------------------------------------
# The plan catalogue
# ----------------------------------------------------------------------


import pytest  # noqa: E402

from bible_tui.services.plan_service import (  # noqa: E402
    CHRONOLOGICAL_ORDER,
    PLAN_KINDS,
    PLAN_KINDS_BY_CODE,
    UnknownPlan,
)

START = date(2026, 1, 1)


@pytest.fixture
def plans(conn):
    return PlanService(conn)


def _scheduled(conn, plan_id):
    """Every (book_id, chapter) the plan schedules, in order."""
    rows = conn.execute(
        """
        SELECT book_id, chapter_start, chapter_end FROM plan_entries
        WHERE plan_id = ? ORDER BY day_number, id
        """,
        (plan_id,),
    ).fetchall()
    return [
        (r["book_id"], c)
        for r in rows
        for c in range(r["chapter_start"], r["chapter_end"] + 1)
    ]


def test_the_chronological_order_names_every_book_exactly_once():
    assert len(CHRONOLOGICAL_ORDER) == 66
    assert sorted(CHRONOLOGICAL_ORDER) == list(range(1, 67))


def test_every_catalogue_entry_has_a_distinct_code():
    codes = [kind.code for kind in PLAN_KINDS]
    assert len(codes) == len(set(codes))
    assert set(codes) == set(PLAN_KINDS_BY_CODE)


@pytest.mark.parametrize("kind", PLAN_KINDS, ids=lambda k: k.code)
def test_every_plan_can_be_started(plans, conn, kind):
    plan_id = plans.create_plan(kind.code, START)
    assert _scheduled(conn, plan_id), f"{kind.code} scheduled nothing"


@pytest.mark.parametrize("kind", PLAN_KINDS, ids=lambda k: k.code)
def test_no_plan_schedules_a_chapter_twice(plans, conn, kind):
    scheduled = _scheduled(conn, plans.create_plan(kind.code, START))
    assert len(scheduled) == len(set(scheduled))


@pytest.mark.parametrize("kind", PLAN_KINDS, ids=lambda k: k.code)
def test_no_plan_runs_past_its_advertised_length(plans, conn, kind):
    plan_id = plans.create_plan(kind.code, START)
    last = conn.execute(
        "SELECT MAX(day_number) AS d FROM plan_entries WHERE plan_id = ?", (plan_id,)
    ).fetchone()["d"]
    assert last <= kind.days


def test_a_whole_bible_plan_covers_every_chapter(plans, conn):
    scheduled = set(_scheduled(conn, plans.create_plan("bible_90", START)))
    total = conn.execute("SELECT SUM(chapter_count) AS n FROM books").fetchone()["n"]
    assert len(scheduled) == total


def test_the_new_testament_plan_stays_in_the_new_testament(plans, conn):
    plan_id = plans.create_plan("nt_90", START)
    testaments = {
        conn.execute("SELECT testament FROM books WHERE id = ?", (b,)).fetchone()["testament"]
        for b, _ in _scheduled(conn, plan_id)
    }
    assert testaments == {"NT"}


def test_the_gospel_plan_is_only_the_four_gospels(plans, conn):
    plan_id = plans.create_plan("gospels_40", START)
    books = {b for b, _ in _scheduled(conn, plan_id)}
    assert books == {40, 41, 42, 43}


def test_the_chronological_plan_starts_in_genesis_and_ends_in_revelation(plans, conn):
    scheduled = _scheduled(conn, plans.create_plan("chronological", START))
    assert scheduled[0] == (1, 1)
    assert scheduled[-1][0] == 66


def test_the_chronological_plan_reads_job_before_exodus(plans, conn):
    # The point of the ordering: Job belongs with the patriarchs, not
    # between Esther and Psalms.
    scheduled = [b for b, _ in _scheduled(conn, plans.create_plan("chronological", START))]
    assert scheduled.index(18) < scheduled.index(2)


def test_the_psalms_plan_reads_a_proverb_a_day_too(plans, conn):
    plan_id = plans.create_plan("psalms_proverbs", START)
    day_one = {e["book_id"] for e in plans.entries_for_day(plan_id, 1)}
    assert day_one == {19, 20}


def test_an_unknown_plan_code_is_refused(plans):
    with pytest.raises(UnknownPlan):
        plans.create_plan("no_such_plan", START)


# ----------------------------------------------------------------------
# Custom plans
# ----------------------------------------------------------------------


def test_a_custom_plan_covers_only_the_chosen_books(plans, conn):
    plan_id = plans.create_custom_plan("Paul's letters", [45, 46], START)
    assert {b for b, _ in _scheduled(conn, plan_id)} == {45, 46}


def test_the_pace_decides_the_length(plans, conn):
    # Romans is 16 chapters; two a day is eight days.
    plan_id = plans.create_custom_plan("Romans", [45], START, chapters_per_day=2)
    last = conn.execute(
        "SELECT MAX(day_number) AS d FROM plan_entries WHERE plan_id = ?", (plan_id,)
    ).fetchone()["d"]
    assert last == 8


def test_a_ragged_pace_still_covers_everything(plans, conn):
    # 16 chapters at 5 a day is four days, the last one short.
    plan_id = plans.create_custom_plan("Romans", [45], START, chapters_per_day=5)
    assert len(_scheduled(conn, plan_id)) == 16


def test_a_custom_plan_needs_at_least_one_real_book(plans):
    with pytest.raises(ValueError):
        plans.create_custom_plan("Nothing", [], START)
    with pytest.raises(ValueError):
        plans.create_custom_plan("Nothing", [9999], START)


def test_a_zero_pace_does_not_divide_by_zero(plans, conn):
    plan_id = plans.create_custom_plan("Romans", [45], START, chapters_per_day=0)
    assert len(_scheduled(conn, plan_id)) == 16


# ----------------------------------------------------------------------
# Switching, restarting and deleting
# ----------------------------------------------------------------------


def test_starting_a_second_plan_makes_it_the_active_one(plans):
    first = plans.create_plan("nt_90", START)
    second = plans.create_plan("gospels_40", START)
    assert plans.active_plan()["id"] == second
    assert {p["id"] for p in plans.list_plans()} == {first, second}


def test_switching_back_does_not_lose_the_other_plan(plans, conn):
    first = plans.create_plan("nt_90", START)
    plans.create_plan("gospels_40", START)
    plans.set_active(first)
    assert plans.active_plan()["id"] == first
    assert len(plans.list_plans()) == 2


def test_only_one_plan_is_ever_active(plans, conn):
    plans.create_plan("nt_90", START)
    plans.create_plan("gospels_40", START)
    active = conn.execute("SELECT COUNT(*) AS n FROM reading_plans WHERE active = 1").fetchone()
    assert active["n"] == 1


def test_deleting_a_plan_takes_its_schedule_with_it(plans, conn):
    plan_id = plans.create_plan("gospels_40", START)
    plans.delete_plan(plan_id)
    assert plans.list_plans() == []
    assert _scheduled(conn, plan_id) == []


def test_restarting_clears_progress_and_resets_the_start_date(plans, conn):
    plan_id = plans.create_plan("gospels_40", date(2020, 1, 1))
    plans.mark_day_complete(plan_id, 1)
    assert plans.progress(plan_id)[0] == 1

    plans.restart_plan(plan_id, START)
    assert plans.progress(plan_id)[0] == 0
    assert plans.current_day_number(plan_id, START) == 1


# ----------------------------------------------------------------------
# Falling behind
# ----------------------------------------------------------------------


def test_a_plan_starting_today_has_nothing_overdue(plans):
    plan_id = plans.create_plan("gospels_40", START)
    assert plans.overdue_entries(plan_id, START) == []
    assert plans.days_behind(plan_id, START) == 0


def test_missed_days_are_reported_oldest_first(plans):
    plan_id = plans.create_plan("gospels_40", START)
    overdue = plans.overdue_entries(plan_id, START + timedelta(days=3))
    assert overdue
    assert [e["day_number"] for e in overdue] == sorted(e["day_number"] for e in overdue)
    assert plans.days_behind(plan_id, START + timedelta(days=3)) == 3


def test_finishing_a_day_clears_it_from_the_backlog(plans):
    plan_id = plans.create_plan("gospels_40", START)
    plans.mark_day_complete(plan_id, 1)
    behind = plans.days_behind(plan_id, START + timedelta(days=3))
    assert behind == 2


def test_todays_reading_is_not_counted_as_overdue(plans):
    plan_id = plans.create_plan("gospels_40", START)
    days = {e["day_number"] for e in plans.overdue_entries(plan_id, START + timedelta(days=2))}
    assert 3 not in days  # day 3 is today


def test_a_plan_dated_in_the_future_reads_as_day_one(plans):
    plan_id = plans.create_plan("gospels_40", date(2030, 1, 1))
    assert plans.current_day_number(plan_id, START) == 1
    assert plans.days_behind(plan_id, START) == 0
