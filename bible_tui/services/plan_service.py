from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Callable

#: A rough chronological ordering of the books, by book_num. It is
#: *book*-level: real chronological plans interleave at chapter level (Job
#: inside Genesis, the psalms among the reigns), which needs a dated
#: concordance this app doesn't ship. Ordering whole books gets most of the
#: benefit - you read the history in the sequence it happened - without
#: inventing scholarship.
CHRONOLOGICAL_ORDER: tuple[int, ...] = (
    1, 18, 2, 3, 4, 5, 6, 7, 8, 9, 19, 10, 13, 20, 21, 22, 11, 14,
    31, 29, 32, 30, 28, 23, 33, 34, 12, 36, 35, 24, 25, 26, 27,
    37, 38, 15, 16, 17, 39,
    42, 40, 41, 43, 44, 59, 48, 52, 53, 46, 47, 45, 49, 51, 57, 50,
    54, 56, 60, 61, 55, 58, 65, 62, 63, 64, 66,
)


@dataclass(frozen=True)
class PlanKind:
    """One entry in the catalogue of plans a reader can start."""

    code: str
    name: str
    description: str
    days: int
    build: Callable[[list[sqlite3.Row], int], list[list[tuple[int, int]]]]

    def chapters_per_day(self, books: list[sqlite3.Row]) -> float:
        return len(self.build(books, self.days)) and sum(
            len(day) for day in self.build(books, self.days)
        ) / self.days


def _chapters(books: list[sqlite3.Row], keep=None, order=None) -> list[tuple[int, int]]:
    """Every chapter of the matching books, as (book_id, chapter) pairs."""
    chosen = [b for b in books if keep is None or keep(b)]
    if order is not None:
        rank = {num: i for i, num in enumerate(order)}
        chosen.sort(key=lambda b: rank.get(b["book_num"], len(rank)))
    return [(b["id"], c) for b in chosen for c in range(1, b["chapter_count"] + 1)]


def _spread(chapters: list[tuple[int, int]], days: int) -> list[list[tuple[int, int]]]:
    """Split a reading list into ``days`` roughly equal days.

    Index arithmetic rather than a fixed chapters-per-day, so the remainder
    is spread across the plan instead of landing as a double-length final
    day nobody finishes.
    """
    if days < 1:
        return [chapters] if chapters else []
    total = len(chapters)

    def edge(day: int) -> int:
        # Ceiling rather than floor, so a list shorter than the plan (the
        # New Testament across a year) starts on day one instead of being
        # rounded off the front.
        return -(-total * day // days)

    return [chapters[edge(d) : edge(d + 1)] for d in range(days)]


def _interleave_ot_and_nt(books: list[sqlite3.Row], days: int) -> list[list[tuple[int, int]]]:
    """Three Old Testament chapters and one New Testament chapter a day.

    The OT is about three times longer, so this rate finishes both together
    and means no day is pure genealogy.
    """
    ot = _chapters(books, lambda b: b["testament"] == "OT")
    nt = _chapters(books, lambda b: b["testament"] == "NT")
    return [a + b for a, b in zip(_spread(ot, days), _spread(nt, days))]


def _chronological(books: list[sqlite3.Row], days: int) -> list[list[tuple[int, int]]]:
    return _spread(_chapters(books, order=CHRONOLOGICAL_ORDER), days)


def _new_testament(books: list[sqlite3.Row], days: int) -> list[list[tuple[int, int]]]:
    return _spread(_chapters(books, lambda b: b["testament"] == "NT"), days)


def _gospels(books: list[sqlite3.Row], days: int) -> list[list[tuple[int, int]]]:
    return _spread(_chapters(books, lambda b: 40 <= b["book_num"] <= 43), days)


def _whole_bible(books: list[sqlite3.Row], days: int) -> list[list[tuple[int, int]]]:
    return _spread(_chapters(books), days)


def _psalms_and_proverbs(books: list[sqlite3.Row], days: int) -> list[list[tuple[int, int]]]:
    """A psalm-and-a-proverb month: five psalms and a proverb a day."""
    psalms = _spread(_chapters(books, lambda b: b["book_num"] == 19), days)
    proverbs = _spread(_chapters(books, lambda b: b["book_num"] == 20), days)
    return [a + b for a, b in zip(psalms, proverbs)]


#: Every plan on offer, in the order they're shown. Adding one means adding
#: a builder and an entry here - nothing else in the app needs to change.
PLAN_KINDS: tuple[PlanKind, ...] = (
    PlanKind(
        "one_year",
        "One Year Bible",
        "The whole Bible in a year, Old and New Testament side by side.",
        365,
        _interleave_ot_and_nt,
    ),
    PlanKind(
        "chronological",
        "Chronological",
        "The whole Bible in a year, in roughly the order events happened.",
        365,
        _chronological,
    ),
    PlanKind(
        "nt_90",
        "New Testament in 90 days",
        "The 260 chapters of the New Testament, about three a day.",
        90,
        _new_testament,
    ),
    PlanKind(
        "gospels_40",
        "The Gospels in 40 days",
        "Matthew through John - a Lent-length read.",
        40,
        _gospels,
    ),
    PlanKind(
        "psalms_proverbs",
        "Psalms and Proverbs",
        "Five psalms and a proverb a day, right through in a month.",
        30,
        _psalms_and_proverbs,
    ),
    PlanKind(
        "bible_90",
        "Bible in 90 days",
        "The whole thing at pace - about thirteen chapters a day.",
        90,
        _whole_bible,
    ),
)

PLAN_KINDS_BY_CODE = {kind.code: kind for kind in PLAN_KINDS}

CUSTOM = "custom"


class UnknownPlan(KeyError):
    """Raised when a plan code has no builder."""


class PlanService:
    """Reading plan generation, progress tracking, and streaks.

    Takes the raw connection rather than BibleRepository because it writes
    to plan-specific tables the repository doesn't otherwise touch, and
    because plan generation is bulk-insert logic rather than a handful of
    parameterized lookups.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------------
    # Starting a plan
    # ------------------------------------------------------------------

    def create_plan(self, code: str, start: date, days: int | None = None) -> int:
        """Start one of the catalogue plans. Returns its id."""
        kind = PLAN_KINDS_BY_CODE.get(code)
        if kind is None:
            raise UnknownPlan(code)
        books = self._books()
        return self._write_plan(kind.name, code, start, kind.build(books, days or kind.days))

    def create_custom_plan(
        self,
        name: str,
        book_ids: list[int],
        start: date,
        chapters_per_day: int = 1,
    ) -> int:
        """A plan over whichever books the reader picked, at their own pace.

        The day count falls out of the pace rather than being asked for
        twice - "two chapters a day" is the thing people actually know.
        """
        by_id = {b["id"]: b for b in self._books()}
        chapters = [
            (book_id, chapter)
            for book_id in book_ids
            if book_id in by_id
            for chapter in range(1, by_id[book_id]["chapter_count"] + 1)
        ]
        if not chapters:
            raise ValueError("a plan needs at least one book")
        pace = max(1, chapters_per_day)
        days = -(-len(chapters) // pace)  # ceiling division
        return self._write_plan(name, CUSTOM, start, _spread(chapters, days))

    def create_one_year_plan(self, start: date) -> int:
        """Kept as the name the rest of the app already calls."""
        return self.create_plan("one_year", start)

    def _books(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT id, book_num, chapter_count, testament FROM books ORDER BY book_num"
        ).fetchall()

    def _write_plan(
        self,
        name: str,
        code: str,
        start: date,
        schedule: list[list[tuple[int, int]]],
    ) -> int:
        """Persist a built schedule. Starting a plan makes it the active one;
        an older plan is left in place but stepped down, so switching plans
        never silently throws away the progress on the old one."""
        self.conn.execute("UPDATE reading_plans SET active = 0")
        plan_id = self.conn.execute(
            "INSERT INTO reading_plans (name, plan_type, start_date, active) VALUES (?, ?, ?, 1)",
            (name, code, start.isoformat()),
        ).lastrowid

        rows = [
            (plan_id, day_number, book_id, chapter_start, chapter_end)
            for day_number, chapters in enumerate(schedule, start=1)
            if chapters
            for book_id, chapter_start, chapter_end in _merge_consecutive_chapters(chapters)
        ]
        self.conn.executemany(
            """
            INSERT INTO plan_entries (plan_id, day_number, book_id, chapter_start, chapter_end)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()
        return plan_id

    # ------------------------------------------------------------------
    # Managing plans
    # ------------------------------------------------------------------

    def list_plans(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM reading_plans ORDER BY active DESC, id DESC"
        ).fetchall()

    def set_active(self, plan_id: int) -> None:
        """Exactly one plan is active at a time - the reader's attention is
        the scarce thing, not the storage."""
        self.conn.execute("UPDATE reading_plans SET active = 0")
        self.conn.execute("UPDATE reading_plans SET active = 1 WHERE id = ?", (plan_id,))
        self.conn.commit()

    def delete_plan(self, plan_id: int) -> None:
        self.conn.execute("DELETE FROM plan_entries WHERE plan_id = ?", (plan_id,))
        self.conn.execute("DELETE FROM reading_plans WHERE id = ?", (plan_id,))
        self.conn.commit()

    def restart_plan(self, plan_id: int, start: date) -> None:
        """Same schedule, clean slate, starting today."""
        self.conn.execute(
            "UPDATE plan_entries SET completed_at = NULL WHERE plan_id = ?", (plan_id,)
        )
        self.conn.execute(
            "UPDATE reading_plans SET start_date = ?, active = 1 WHERE id = ?",
            (start.isoformat(), plan_id),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Falling behind
    # ------------------------------------------------------------------

    def overdue_entries(self, plan_id: int, today: date | None = None) -> list[dict]:
        """Everything scheduled before today and still unread, oldest first.

        A plan without a catch-up view is a plan you abandon the first week
        you miss - this is what makes it recoverable.
        """
        day_number = self.current_day_number(plan_id, today)
        rows = self.conn.execute(
            """
            SELECT pe.*, b.name AS book_name
            FROM plan_entries pe JOIN books b ON pe.book_id = b.id
            WHERE pe.plan_id = ? AND pe.day_number < ? AND pe.completed_at IS NULL
            ORDER BY pe.day_number, pe.id
            """,
            (plan_id, max(1, day_number)),
        ).fetchall()
        return [dict(r) for r in rows]

    def days_behind(self, plan_id: int, today: date | None = None) -> int:
        rows = self.overdue_entries(plan_id, today)
        return len({r["day_number"] for r in rows})

    def mark_day_complete(self, plan_id: int, day_number: int) -> None:
        self.conn.execute(
            """
            UPDATE plan_entries SET completed_at = datetime('now')
            WHERE plan_id = ? AND day_number = ? AND completed_at IS NULL
            """,
            (plan_id, day_number),
        )
        self.conn.commit()

    # ------------------------------------------------------------------

    def entries_for_day(self, plan_id: int, day_number: int) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT pe.*, b.name AS book_name
            FROM plan_entries pe
            JOIN books b ON pe.book_id = b.id
            WHERE pe.plan_id = ? AND pe.day_number = ?
            """,
            (plan_id, day_number),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_complete(self, entry_id: int) -> None:
        self.conn.execute(
            "UPDATE plan_entries SET completed_at = datetime('now') WHERE id = ?", (entry_id,)
        )
        self.conn.commit()

    def active_plan(self) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM reading_plans WHERE active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()

    def current_day_number(self, plan_id: int, today: date | None = None) -> int:
        """Which day of the plan it is. Clamped at 1 so a plan dated in the
        future reads as "not started" rather than day zero or negative."""
        plan = self.conn.execute(
            "SELECT start_date FROM reading_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if plan is None:
            return 1
        start = date.fromisoformat(plan["start_date"])
        return max(1, ((today or date.today()) - start).days + 1)

    def progress(self, plan_id: int) -> tuple[int, int]:
        """Returns (completed_days, total_days)."""
        rows = self.conn.execute(
            """
            SELECT day_number, COUNT(*) AS total,
                   SUM(CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END) AS done
            FROM plan_entries WHERE plan_id = ? GROUP BY day_number
            """,
            (plan_id,),
        ).fetchall()
        completed = sum(1 for r in rows if r["done"] == r["total"])
        return completed, len(rows)

    def current_streak(self, plan_id: int) -> int:
        """Counts consecutive completed days working backward from today,
        where a day counts as done only if every entry for that day is done."""
        rows = self.conn.execute(
            """
            SELECT day_number, COUNT(*) AS total,
                   SUM(CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END) AS done
            FROM plan_entries WHERE plan_id = ? GROUP BY day_number ORDER BY day_number
            """,
            (plan_id,),
        ).fetchall()
        completed_days = {r["day_number"] for r in rows if r["done"] == r["total"]}

        today_day_number = self.current_day_number(plan_id)

        streak = 0
        d = today_day_number
        while d in completed_days:
            streak += 1
            d -= 1
        return streak


def _merge_consecutive_chapters(
    chapters: list[tuple[int, int]],
) -> list[tuple[int, int, int]]:
    """Merges a list of (book_id, chapter) pairs into (book_id, start, end)
    ranges wherever consecutive entries share a book and increment by one."""
    if not chapters:
        return []
    merged = []
    book_id, start = chapters[0]
    end = start
    for b, c in chapters[1:]:
        if b == book_id and c == end + 1:
            end = c
        else:
            merged.append((book_id, start, end))
            book_id, start, end = b, c, c
    merged.append((book_id, start, end))
    return merged
