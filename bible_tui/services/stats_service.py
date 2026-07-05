"""What the reader has actually read.

Everything here is derived from one append-only table, ``reading_events``,
holding a row per chapter read. Deriving rather than tallying means a
surprising number can be traced back to the readings behind it, and a
statistic nobody thought of yet can be added without a backfill.

The one judgement call is what counts as *read*. Paging through chapters
with ``]`` to reach the one you want should not earn credit, so a visit
shorter than :data:`MINIMUM_SECONDS` is dropped rather than recorded.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass

# Same tokenizer as reading_mode_service's memorise/dictate drills - one
# definition of "a word" for this app, reused rather than redefined.
from .reading_mode_service import _WORD_RE

#: Below this, a chapter was passed through rather than read.
MINIMUM_SECONDS = 5

#: How far back the activity chart looks by default.
_RECENT_DAYS = 30

#: Overall-Bible and streak thresholds a milestone toast fires at.
MILESTONE_PERCENTAGES = (25, 50, 75, 100)
MILESTONE_STREAK_DAYS = (7, 30, 100)

_GOAL_SETTING_KEY = "stats_goal"


@dataclass(frozen=True)
class Totals:
    chapters: int = 0
    unique_chapters: int = 0
    verses: int = 0
    seconds: int = 0
    days: int = 0
    first_day: str | None = None

    @property
    def minutes(self) -> int:
        return self.seconds // 60

    def describe_time(self) -> str:
        if self.seconds < 60:
            return f"{self.seconds}s"
        if self.seconds < 3600:
            return f"{self.seconds // 60}m"
        hours, remainder = divmod(self.seconds, 3600)
        return f"{hours}h {remainder // 60}m"

    @property
    def average_seconds_per_chapter(self) -> int:
        return self.seconds // self.chapters if self.chapters else 0


@dataclass(frozen=True)
class Streak:
    current: int = 0
    longest: int = 0
    read_today: bool = False

    def describe(self) -> str:
        if not self.current:
            if self.longest:
                # Telling someone with a 12-day record that they have "no
                # streak yet" erases the reading they actually did.
                return "Broken - read today to start again"
            return "No streak yet - read a chapter to start one"
        day = "day" if self.current == 1 else "days"
        if not self.read_today:
            return f"{self.current} {day} (read today to keep it)"
        return f"{self.current} {day}"


@dataclass(frozen=True)
class BookProgress:
    book_id: int
    name: str
    testament: str
    chapters_read: int
    chapter_count: int

    @property
    def is_complete(self) -> bool:
        return self.chapters_read >= self.chapter_count

    @property
    def fraction(self) -> float:
        if not self.chapter_count:
            return 0.0
        return min(1.0, self.chapters_read / self.chapter_count)

    @property
    def percent(self) -> int:
        return round(self.fraction * 100)


@dataclass(frozen=True)
class Coverage:
    books: tuple[BookProgress, ...] = ()

    @property
    def chapters_read(self) -> int:
        return sum(b.chapters_read for b in self.books)

    @property
    def chapters_total(self) -> int:
        return sum(b.chapter_count for b in self.books)

    @property
    def books_complete(self) -> int:
        return sum(1 for b in self.books if b.is_complete)

    @property
    def books_started(self) -> int:
        return sum(1 for b in self.books if b.chapters_read)

    @property
    def percent(self) -> float:
        if not self.chapters_total:
            return 0.0
        return 100.0 * self.chapters_read / self.chapters_total

    def testament(self, code: str) -> Coverage:
        return Coverage(tuple(b for b in self.books if b.testament == code))


@dataclass(frozen=True)
class VerseExtreme:
    reference: str
    words: int


@dataclass
class StatsService:
    conn: sqlite3.Connection
    minimum_seconds: int = MINIMUM_SECONDS

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        book_id: int,
        chapter: int,
        translation_code: str,
        *,
        seconds: int,
        verses: int = 0,
        when: dt.datetime | None = None,
    ) -> bool:
        """Log one chapter read. Returns whether it counted."""
        if seconds < self.minimum_seconds:
            return False
        moment = when or dt.datetime.now()
        self.conn.execute(
            """
            INSERT INTO reading_events
                (book_id, chapter, translation_code, read_on, started_at, seconds, verses)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book_id,
                chapter,
                translation_code,
                moment.date().isoformat(),
                moment.isoformat(timespec="seconds"),
                int(seconds),
                int(verses),
            ),
        )
        self.conn.commit()
        return True

    def forget_everything(self) -> None:
        """For someone who wants their numbers to start from today."""
        self.conn.execute("DELETE FROM reading_events")
        self.conn.commit()

    # ------------------------------------------------------------------
    # Derived numbers
    # ------------------------------------------------------------------

    def totals(self) -> Totals:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS chapters,
                   COUNT(DISTINCT book_id || ':' || chapter) AS unique_chapters,
                   COALESCE(SUM(verses), 0) AS verses,
                   COALESCE(SUM(seconds), 0) AS seconds,
                   COUNT(DISTINCT read_on) AS days,
                   MIN(read_on) AS first_day
            FROM reading_events
            """
        ).fetchone()
        return Totals(
            chapters=row["chapters"],
            unique_chapters=row["unique_chapters"],
            verses=row["verses"],
            seconds=row["seconds"],
            days=row["days"],
            first_day=row["first_day"],
        )

    def streak(self, today: dt.date | None = None) -> Streak:
        """Consecutive days with at least one chapter read.

        Yesterday still counts towards the current streak - a streak should
        not be reported as broken before the day it was actually missed.
        """
        today = today or dt.date.today()
        days = self._active_days()
        if not days:
            return Streak()

        longest = run = 1
        for previous, current in zip(days, days[1:]):
            run = run + 1 if (current - previous).days == 1 else 1
            longest = max(longest, run)

        last = days[-1]
        gap = (today - last).days
        if gap > 1:
            return Streak(current=0, longest=longest, read_today=False)

        current = 1
        for previous, following in zip(reversed(days[:-1]), reversed(days[1:])):
            if (following - previous).days != 1:
                break
            current += 1
        return Streak(current=current, longest=longest, read_today=gap == 0)

    def coverage(self) -> Coverage:
        rows = self.conn.execute(
            """
            SELECT b.id, b.name, b.testament, b.chapter_count,
                   COUNT(DISTINCT e.chapter) AS chapters_read
            FROM books b
            LEFT JOIN reading_events e ON e.book_id = b.id
            GROUP BY b.id
            ORDER BY b.book_num
            """
        ).fetchall()
        return Coverage(
            tuple(
                BookProgress(
                    book_id=r["id"],
                    name=r["name"],
                    testament=r["testament"],
                    chapters_read=r["chapters_read"],
                    chapter_count=r["chapter_count"],
                )
                for r in rows
            )
        )

    def most_read(self, limit: int = 5) -> list[tuple[str, int]]:
        rows = self.conn.execute(
            """
            SELECT b.name, COUNT(*) AS visits
            FROM reading_events e JOIN books b ON b.id = e.book_id
            GROUP BY e.book_id
            ORDER BY visits DESC, b.book_num
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [(r["name"], r["visits"]) for r in rows]

    def daily_activity(self, days: int = _RECENT_DAYS, today: dt.date | None = None) -> list[tuple[dt.date, int]]:
        """Chapters per day for the last ``days`` days, gaps included.

        Empty days are returned as zeroes rather than omitted, so a caller
        drawing a bar chart doesn't have to reconstruct the calendar.
        """
        today = today or dt.date.today()
        start = today - dt.timedelta(days=days - 1)
        rows = self.conn.execute(
            "SELECT read_on, COUNT(*) AS n FROM reading_events WHERE read_on >= ? GROUP BY read_on",
            (start.isoformat(),),
        ).fetchall()
        counted = {r["read_on"]: r["n"] for r in rows}
        return [
            (start + dt.timedelta(days=offset), counted.get((start + dt.timedelta(days=offset)).isoformat(), 0))
            for offset in range(days)
        ]

    def history(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT e.read_on, e.started_at, e.chapter, e.seconds, e.verses,
                   b.name AS book_name
            FROM reading_events e JOIN books b ON b.id = e.book_id
            ORDER BY e.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def pace(self) -> str:
        """How long finishing the Bible would take at the current rate."""
        totals = self.totals()
        coverage = self.coverage()
        remaining = coverage.chapters_total - coverage.chapters_read
        if not remaining:
            return "You have read every chapter"
        if not totals.days or not totals.chapters:
            return "Not enough reading yet to estimate"
        per_day = totals.chapters / totals.days
        days = remaining / per_day
        if days < 60:
            return f"About {round(days)} days to finish at this pace"
        if days < 730:
            return f"About {round(days / 30.4)} months to finish at this pace"
        return f"About {days / 365.25:.1f} years to finish at this pace"

    # ------------------------------------------------------------------
    # Word-level stats: vocabulary, frequency, words-per-minute
    # ------------------------------------------------------------------

    def _words_by_chapter(self) -> dict[tuple[int, int, str], list[str]]:
        """Every distinct (book, chapter, translation) actually read, at
        least once, mapped to its lower-cased word list. Reading-scoped -
        the same ethos as time tracking only counting chapters lingered
        on: this is "words you've actually been exposed to," not the
        whole Bible's vocabulary."""
        rows = self.conn.execute(
            """
            SELECT v.book_id, v.chapter, e.translation_code AS translation_code, v.text
            FROM verses v
            JOIN (
                SELECT DISTINCT book_id, chapter, translation_code FROM reading_events
            ) e ON v.book_id = e.book_id AND v.chapter = e.chapter
            JOIN translations t ON v.translation_id = t.id AND t.code = e.translation_code
            """
        ).fetchall()
        by_chapter: dict[tuple[int, int, str], list[str]] = {}
        for row in rows:
            key = (row["book_id"], row["chapter"], row["translation_code"])
            by_chapter.setdefault(key, []).extend(w.lower() for w in _WORD_RE.findall(row["text"]))
        return by_chapter

    def word_frequency(self, limit: int = 20) -> list[tuple[str, int]]:
        counts: Counter[str] = Counter()
        for words in self._words_by_chapter().values():
            counts.update(words)
        return counts.most_common(limit)

    def unique_vocabulary_count(self) -> int:
        vocabulary: set[str] = set()
        for words in self._words_by_chapter().values():
            vocabulary.update(words)
        return len(vocabulary)

    def words_per_minute(self) -> float:
        """Unlike vocabulary/frequency, a chapter read twice counts its
        words twice here - it really did cost minutes each time - so this
        sums per *event*, not per distinct chapter."""
        totals = self.totals()
        if totals.minutes <= 0:
            return 0.0
        by_chapter = self._words_by_chapter()
        events = self.conn.execute(
            "SELECT book_id, chapter, translation_code FROM reading_events"
        ).fetchall()
        total_words = sum(
            len(by_chapter.get((e["book_id"], e["chapter"], e["translation_code"]), ()))
            for e in events
        )
        return total_words / totals.minutes

    def verse_length_stats(self, translation_code: str) -> tuple[VerseExtreme, VerseExtreme, float]:
        """Shortest verse, longest verse, and the average verse length in
        words, across the whole Bible in `translation_code`. Not
        reading-scoped - this describes the text itself, not what's been
        read of it."""
        rows = self.conn.execute(
            """
            SELECT b.name AS book_name, v.chapter, v.verse, v.text
            FROM verses v
            JOIN translations t ON v.translation_id = t.id
            JOIN books b ON v.book_id = b.id
            WHERE t.code = ?
            """,
            (translation_code,),
        ).fetchall()
        if not rows:
            empty = VerseExtreme("", 0)
            return empty, empty, 0.0
        shortest: VerseExtreme | None = None
        longest: VerseExtreme | None = None
        total_words = 0
        for row in rows:
            words = len(_WORD_RE.findall(row["text"]))
            total_words += words
            extreme = VerseExtreme(f"{row['book_name']} {row['chapter']}:{row['verse']}", words)
            if shortest is None or words < shortest.words:
                shortest = extreme
            if longest is None or words > longest.words:
                longest = extreme
        return shortest, longest, total_words / len(rows)

    # ------------------------------------------------------------------
    # Weekly summary and milestones
    # ------------------------------------------------------------------

    def weekly_activity(self, weeks: int = 8, today: dt.date | None = None) -> list[tuple[dt.date, int]]:
        """Chapters read per ISO week, oldest first, zero-filled like
        daily_activity() - each entry is the Monday that starts the week."""
        today = today or dt.date.today()
        this_monday = today - dt.timedelta(days=today.weekday())
        week_starts = [this_monday - dt.timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
        rows = self.conn.execute(
            "SELECT read_on, COUNT(*) AS n FROM reading_events WHERE read_on >= ? GROUP BY read_on",
            (week_starts[0].isoformat(),),
        ).fetchall()
        per_day = {row["read_on"]: row["n"] for row in rows}
        result: list[tuple[dt.date, int]] = []
        for start in week_starts:
            total = sum(
                per_day.get((start + dt.timedelta(days=offset)).isoformat(), 0)
                for offset in range(7)
                if start + dt.timedelta(days=offset) <= today
            )
            result.append((start, total))
        return result

    def check_milestones(
        self, before_coverage: Coverage, before_streak: Streak, today: dt.date | None = None
    ) -> list[str]:
        """Compare a snapshot taken just before a `record()` call against
        the current state, returning a message for anything newly
        crossed. Call this right after `record()`, with the coverage/
        streak captured right before it - a threshold is naturally only
        ever "just crossed" once, so nothing needs to be remembered
        between calls."""
        after_coverage = self.coverage()
        after_streak = self.streak(today)
        messages: list[str] = []
        for pct in MILESTONE_PERCENTAGES:
            if before_coverage.percent < pct <= after_coverage.percent:
                messages.append(f"{pct}% of the Bible read!")
        before_by_id = {b.book_id: b for b in before_coverage.books}
        for book in after_coverage.books:
            was_complete = before_by_id.get(book.book_id)
            if book.is_complete and not (was_complete and was_complete.is_complete):
                messages.append(f"{book.name} complete!")
        for days in MILESTONE_STREAK_DAYS:
            if before_streak.current < days <= after_streak.current:
                messages.append(f"{days}-day reading streak!")
        return messages

    # ------------------------------------------------------------------
    # Reading goals
    # ------------------------------------------------------------------

    def set_goal(self, kind: str, target: int) -> None:
        """`kind` is 'minutes' or 'chapters', `target` is the daily amount."""
        self.conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (_GOAL_SETTING_KEY, json.dumps({"kind": kind, "target": target})),
        )
        self.conn.commit()

    def clear_goal(self) -> None:
        self.conn.execute("DELETE FROM settings WHERE key = ?", (_GOAL_SETTING_KEY,))
        self.conn.commit()

    def get_goal(self) -> dict | None:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (_GOAL_SETTING_KEY,)
        ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["value"])
        except (TypeError, ValueError):
            return None

    def goal_progress_today(self, today: dt.date | None = None) -> tuple[int, int, str] | None:
        """(progress, target, kind) against today's saved goal, or None if
        no goal is set."""
        goal = self.get_goal()
        if not goal:
            return None
        today = (today or dt.date.today()).isoformat()
        row = self.conn.execute(
            "SELECT COUNT(*) AS chapters, COALESCE(SUM(seconds), 0) AS seconds "
            "FROM reading_events WHERE read_on = ?",
            (today,),
        ).fetchone()
        if goal["kind"] == "chapters":
            return row["chapters"], goal["target"], "chapters"
        return row["seconds"] // 60, goal["target"], "minutes"

    # ------------------------------------------------------------------

    def _active_days(self) -> list[dt.date]:
        rows = self.conn.execute(
            "SELECT DISTINCT read_on FROM reading_events ORDER BY read_on"
        ).fetchall()
        days: list[dt.date] = []
        for row in rows:
            try:
                days.append(dt.date.fromisoformat(row["read_on"]))
            except (TypeError, ValueError):
                continue  # a hand-edited or imported row shouldn't break the screen
        return days
