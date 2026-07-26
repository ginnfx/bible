"""The reading record: what has been read, how consistently, how much is left.

Laid out as four blocks - a headline, a streak, the last month's activity,
and per-book progress - because those answer the four questions people
actually ask of a reading tracker, in that order.

The bars are drawn from block characters rather than Textual's ProgressBar
so that sixty-six of them can sit in one scrollable column without sixty-six
widgets, and so the whole screen renders identically over SSH.
"""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...services.stats_service import Coverage, StatsService
from .prompt import PromptModal

#: Widths chosen so the widest book name ("Song of Solomon") and a full bar
#: both fit inside an 80-column terminal.
_BAR_WIDTH = 24
_NAME_WIDTH = 18

_FULL = "█"
_EMPTY = "░"

#: Eight levels of shading for the activity chart, quietest first. Index 0
#: is reserved for days with no reading at all - a dot rather than a blank,
#: so a chart of the last thirty days still looks thirty days wide when
#: only a handful of them were busy.
_SPARK = "·▁▂▃▄▅▆▇█"


def bar(fraction: float, width: int = _BAR_WIDTH) -> str:
    """A fixed-width bar. Any progress at all shows at least one cell, so a
    book that has been started never looks untouched."""
    fraction = max(0.0, min(1.0, fraction))
    filled = round(fraction * width)
    if fraction > 0 and filled == 0:
        filled = 1
    return _FULL * filled + _EMPTY * (width - filled)


def sparkline(counts: list[int]) -> str:
    """Scaled to its own busiest day, so a light month still reads as a
    shape rather than a flat line."""
    if not counts:
        return ""
    peak = max(counts)
    if not peak:
        return _SPARK[0] * len(counts)
    return "".join(_SPARK[min(len(_SPARK) - 1, 1 + round(c / peak * (len(_SPARK) - 2)))] if c else _SPARK[0] for c in counts)


def axis(first, last, width: int) -> str:
    """Date labels under a chart of ``width`` cells: the first sits under the
    oldest day, the last ends under the newest, so the two ends of the label
    line mean the two ends of the chart."""
    left = first.strftime("%b %d")
    right = last.strftime("%b %d")
    gap = width - len(left) - len(right)
    if gap < 1:
        return right.rjust(width)
    return left + " " * gap + right


def _parse_goal(text: str) -> tuple[str, int] | None:
    """'20 minutes', '20m', '3 chapters', '3c', or a bare number (minutes)
    -> ('minutes' | 'chapters', target). Blank or unreadable -> None."""
    text = text.strip().lower()
    if not text:
        return None
    match = re.match(r"^(\d+)\s*([a-z]*)$", text)
    if not match:
        return None
    target = int(match.group(1))
    if target <= 0:
        return None
    unit = match.group(2)
    if unit.startswith("c"):
        return "chapters", target
    if unit.startswith("m") or unit == "":
        return "minutes", target
    return None


class StatsScreen(Screen[None]):
    """Read-only. Everything on it comes from the reading_events table."""

    BINDINGS = [
        ("escape,q", "close", "Back"),
        ("r", "reset", "Reset"),
        ("g", "set_goal", "Goal"),
    ]

    DEFAULT_CSS = """
    StatsScreen VerticalScroll { padding: 1 2; }
    /* Vertical is 1fr by default, which would clamp the body to the
       viewport and clip the book list instead of letting it scroll. */
    StatsScreen #stats-body { height: auto; }
    StatsScreen .stats-heading {
        text-style: bold;
        color: $text-accent;
        margin: 1 0 0 0;
    }
    StatsScreen .stats-block { margin: 0 0 1 0; }
    StatsScreen #stats-empty { padding: 2 0; color: $text-muted; }
    """

    def __init__(self, stats: StatsService):
        super().__init__()
        self.stats = stats
        self._confirming_reset = False

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            with Vertical(id="stats-body"):
                yield Static("", id="stats-empty")
                yield Static("Overall", classes="stats-heading", id="h-overall")
                yield Static("", classes="stats-block", id="stats-overall")
                yield Static("Consistency", classes="stats-heading", id="h-streak")
                yield Static("", classes="stats-block", id="stats-streak")
                yield Static("Last 30 days", classes="stats-heading", id="h-activity")
                yield Static("", classes="stats-block", id="stats-activity")
                yield Static("Last 8 weeks", classes="stats-heading", id="h-weekly")
                yield Static("", classes="stats-block", id="stats-weekly")
                yield Static("Words", classes="stats-heading", id="h-words")
                yield Static("", classes="stats-block", id="stats-words")
                yield Static("Progress through the Bible", classes="stats-heading", id="h-books")
                yield Static("", classes="stats-block", id="stats-books")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#stats-body").border_title = "Reading record"
        self._refresh()

    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        # Not `_render` - that is Textual's own hook on Widget, and shadowing
        # it makes the screen render as nothing at all.
        totals = self.stats.totals()
        empty = self.query_one("#stats-empty", Static)
        has_reading = totals.chapters > 0

        empty.display = not has_reading
        for widget_id in ("h-overall", "stats-overall", "h-streak", "stats-streak",
                          "h-activity", "stats-activity", "h-weekly", "stats-weekly",
                          "h-words", "stats-words", "h-books", "stats-books"):
            self.query_one(f"#{widget_id}", Static).display = has_reading

        if not has_reading:
            empty.update(
                "Nothing recorded yet.\n\n"
                "Every chapter you spend a moment on is counted from here on - "
                "streaks, coverage and pace all follow from that."
            )
            return

        coverage = self.stats.coverage()
        self.query_one("#stats-overall", Static).update(self._overall(totals, coverage))
        self.query_one("#stats-streak", Static).update(self._streak())
        self.query_one("#stats-activity", Static).update(self._activity())
        self.query_one("#stats-weekly", Static).update(self._weekly())
        self.query_one("#stats-words", Static).update(self._words())
        self.query_one("#stats-books", Static).update(self._books(coverage))

    def _overall(self, totals, coverage: Coverage) -> str:
        lines = [
            f"{bar(coverage.percent / 100)}  {coverage.percent:.1f}% of the Bible",
            "",
            f"  Chapters read     {coverage.chapters_read} of {coverage.chapters_total}"
            f"  ({totals.chapters} visits)",
            f"  Books finished    {coverage.books_complete} of {len(coverage.books)}"
            f"  ({coverage.books_started} started)",
            f"  Verses read       {totals.verses}",
            f"  Time reading      {totals.describe_time()}"
            f"  (about {totals.average_seconds_per_chapter}s a chapter)",
        ]
        if totals.first_day:
            day = "day" if totals.days == 1 else "days"
            lines.append(
                f"  Reading since     {totals.first_day}  (on {totals.days} {day})"
            )
        lines.append(f"\n  [$text-accent]{self.stats.pace()}[/]")
        progress = self.stats.goal_progress_today()
        if progress is not None:
            done, target, kind = progress
            met = "[$success]✓[/]" if done >= target else ""
            lines.append(f"  Today's goal      {done}/{target} {kind} {met}  (g to change)")
        else:
            lines.append("  [$text-disabled]No daily goal set - press g to set one[/]")
        return "\n".join(lines)

    def _weekly(self) -> str:
        weeks = self.stats.weekly_activity(weeks=8)
        counts = [n for _, n in weeks]
        busiest = max(counts) if any(counts) else 1
        lines = []
        for start, count in weeks:
            lines.append(f"  {start.isoformat()}  {bar(count / busiest, 12)}  {count}")
        return "\n".join(lines)

    def _words(self) -> str:
        wpm = self.stats.words_per_minute()
        vocab = self.stats.unique_vocabulary_count()
        freq = self.stats.word_frequency(limit=8)
        translation_code = getattr(self.app, "config", None)
        translation_code = translation_code.translation_code if translation_code else "KJV"
        shortest, longest, average = self.stats.verse_length_stats(translation_code)
        lines = [
            f"  Reading pace      {wpm:.0f} words/min" if wpm else "  Reading pace      not enough data yet",
            f"  Vocabulary seen   {vocab} distinct words",
        ]
        if freq:
            common = ", ".join(f"{word} ({n})" for word, n in freq)
            lines.append(f"  Most common       {common}")
        lines.append(
            f"  Verse extremes    shortest {shortest.reference} ({shortest.words}w),"
            f" longest {longest.reference} ({longest.words}w), average {average:.1f}w"
        )
        return "\n".join(lines)

    def _streak(self) -> str:
        streak = self.stats.streak()
        lines = [f"  Current streak    {streak.describe()}"]
        if streak.longest:
            lines.append(f"  Longest streak    {streak.longest} days")
        most_read = self.stats.most_read(5)
        if most_read:
            lines.append("\n  Most read")
            widest = max(len(name) for name, _ in most_read)
            busiest = max(count for _, count in most_read)
            for name, count in most_read:
                lines.append(
                    f"    {name.ljust(widest)}  {bar(count / busiest, 12)}  {count}"
                )
        return "\n".join(lines)

    def _activity(self) -> str:
        activity = self.stats.daily_activity()
        counts = [count for _, count in activity]
        busiest = max(counts)
        return (
            f"  {sparkline(counts)}\n"
            f"  {axis(activity[0][0], activity[-1][0], len(counts))}\n\n"
            f"  {sum(counts)} chapters on {sum(1 for c in counts if c)} of the last "
            f"{len(counts)} days  (busiest: {busiest})"
        )

    def _books(self, coverage: Coverage) -> str:
        lines = []
        for testament, title in (("OT", "Old Testament"), ("NT", "New Testament")):
            part = coverage.testament(testament)
            if not part.books:
                continue
            lines.append(
                f"\n  [b]{title}[/]  {part.chapters_read}/{part.chapters_total}"
                f"  ({part.percent:.0f}%)"
            )
            for book in part.books:
                marker = "[$success]✓[/]" if book.is_complete else " "
                name = book.name[:_NAME_WIDTH].ljust(_NAME_WIDTH)
                style = "" if book.chapters_read else "[$text-disabled]"
                close = "" if book.chapters_read else "[/]"
                lines.append(
                    f"  {marker} {style}{name} {bar(book.fraction)} "
                    f"{book.chapters_read:>3}/{book.chapter_count:<3}{close}"
                )
        return "\n".join(lines)

    # ------------------------------------------------------------------

    def action_close(self) -> None:
        self.dismiss(None)

    def action_set_goal(self) -> None:
        current = self.stats.get_goal()
        initial = f"{current['target']} {current['kind']}" if current else ""
        self.app.push_screen(
            PromptModal("Daily goal (e.g. '20 minutes' or '3 chapters', blank to clear)", initial),
            self._apply_goal,
        )

    def _apply_goal(self, text: str | None) -> None:
        if text is None:
            return
        parsed = _parse_goal(text)
        if text.strip() and parsed is None:
            self.notify("Couldn't read that goal - try '20 minutes' or '3 chapters'.", severity="warning")
            return
        if parsed is None:
            self.stats.clear_goal()
        else:
            kind, target = parsed
            self.stats.set_goal(kind, target)
        self._refresh()

    def action_reset(self) -> None:
        """Two presses, because there is no undo for this one."""
        if not self._confirming_reset:
            self._confirming_reset = True
            self.notify(
                "Press r again to erase your entire reading record.",
                severity="warning",
                timeout=5,
            )
            return
        self._confirming_reset = False
        self.stats.forget_everything()
        self._refresh()
        self.notify("Reading record cleared.")
