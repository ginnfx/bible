"""Reading plans: what to read today, how far behind you are, and how to
start, switch, restart or abandon a plan.

Two modes on one screen. With a plan running it shows today's reading (and
the backlog, if there is one); with none it shows the catalogue. Selecting a
reading marks it done and dismisses with (book_id, chapter) so the reader
jumps straight there - finishing the list should feel like reading, not
like ticking boxes.
"""

from __future__ import annotations

from datetime import date

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from ...services.plan_service import PLAN_KINDS, PlanService

_CATALOGUE = "catalogue"
_TODAY = "today"


class PlansScreen(Screen[tuple[int, int] | None]):
    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("n", "show_catalogue", "New plan"),
        Binding("c", "toggle_catch_up", "Catch up"),
        Binding("x", "restart", "Restart"),
        Binding("D", "abandon", "Abandon"),
        Binding("s", "switch", "Switch"),
    ]

    DEFAULT_CSS = """
    PlansScreen Vertical { padding: 1 2; }
    PlansScreen #plan-summary { margin-bottom: 1; }
    PlansScreen #plan-hint { color: $text-muted; margin-bottom: 1; }
    PlansScreen #plan-entries { height: 1fr; }
    """

    def __init__(self, plans: PlanService):
        super().__init__()
        self.plans = plans
        self.mode = _TODAY
        self.showing_catch_up = False
        self._entries: list[dict] = []
        self._plan_id: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("", id="plan-summary")
            yield Static("", id="plan-hint")
            yield ListView(id="plan-entries")
        yield Footer()

    def on_mount(self) -> None:
        plan = self.plans.active_plan()
        self.mode = _TODAY if plan else _CATALOGUE
        self._refresh()
        self.query_one("#plan-entries", ListView).focus()

    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        entries = self.query_one("#plan-entries", ListView)
        entries.clear()
        self._entries = []
        if self.mode == _CATALOGUE:
            self._show_catalogue(entries)
        else:
            self._show_today(entries)
        entries.index = 0

    def _show_catalogue(self, entries: ListView) -> None:
        self.query_one("#plan-summary", Static).update("[b]Choose a reading plan[/]")
        self.query_one("#plan-hint", Static).update(
            "Starting a plan pauses any other one - your progress on it is kept."
        )
        for kind in PLAN_KINDS:
            entries.append(
                ListItem(
                    Label(
                        f"[b]{kind.name}[/]  [$text-disabled]{kind.days} days[/]\n"
                        f"  [$text-muted]{kind.description}[/]"
                    )
                )
            )

    def _show_today(self, entries: ListView) -> None:
        plan = self.plans.active_plan()
        if plan is None:
            self.mode = _CATALOGUE
            self._show_catalogue(entries)
            return

        self._plan_id = plan["id"]
        day = self.plans.current_day_number(plan["id"])
        streak = self.plans.current_streak(plan["id"])
        done, total = self.plans.progress(plan["id"])
        behind = self.plans.days_behind(plan["id"])

        summary = (
            f"[b]{plan['name']}[/]  ·  day {day}  ·  {done}/{total} days done"
            f"  ·  streak {streak}"
        )
        if behind:
            summary += f"  ·  [$warning]{behind} day(s) behind[/]"
        self.query_one("#plan-summary", Static).update(summary)

        if self.showing_catch_up:
            self._entries = self.plans.overdue_entries(plan["id"])
            self.query_one("#plan-hint", Static).update(
                "Everything you've missed, oldest first - c returns to today."
            )
        else:
            self._entries = self.plans.entries_for_day(plan["id"], day)
            self.query_one("#plan-hint", Static).update(
                f"Today's reading - c shows the {behind} day(s) you're behind."
                if behind
                else "Today's reading. Choose one to read it and mark it done."
            )

        if not self._entries:
            entries.append(
                ListItem(
                    Label(
                        "[$text-disabled]Nothing left here - the plan may be "
                        "finished, or you're all caught up.[/]"
                    )
                )
            )
            return

        for entry in self._entries:
            mark = "[$success]✓[/]" if entry["completed_at"] else "○"
            span = (
                f"{entry['book_name']} {entry['chapter_start']}"
                if entry["chapter_start"] == entry["chapter_end"]
                else f"{entry['book_name']} {entry['chapter_start']}–{entry['chapter_end']}"
            )
            day_note = (
                f"  [$text-disabled]day {entry['day_number']}[/]"
                if self.showing_catch_up
                else ""
            )
            entries.append(ListItem(Label(f"{mark} {span}{day_note}")))

    # ------------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        if index is None:
            return
        if self.mode == _CATALOGUE:
            if 0 <= index < len(PLAN_KINDS):
                self.plans.create_plan(PLAN_KINDS[index].code, date.today())
                self.mode = _TODAY
                self.showing_catch_up = False
                self._refresh()
            return
        if not (0 <= index < len(self._entries)):
            return
        entry = self._entries[index]
        self.plans.mark_complete(entry["id"])
        self.dismiss((entry["book_id"], entry["chapter_start"]))

    # ------------------------------------------------------------------

    def action_close(self) -> None:
        self.dismiss(None)

    def action_show_catalogue(self) -> None:
        self.mode = _CATALOGUE
        self._refresh()

    def action_toggle_catch_up(self) -> None:
        if self.mode != _TODAY:
            return
        self.showing_catch_up = not self.showing_catch_up
        self._refresh()

    def action_restart(self) -> None:
        if self._plan_id is None or self.mode != _TODAY:
            return
        self.plans.restart_plan(self._plan_id, date.today())
        self.showing_catch_up = False
        self._refresh()
        self.notify("Plan restarted from today.")

    def action_abandon(self) -> None:
        if self._plan_id is None or self.mode != _TODAY:
            return
        self.plans.delete_plan(self._plan_id)
        self._plan_id = None
        self.mode = _CATALOGUE
        self._refresh()
        self.notify("Plan abandoned.")

    def action_switch(self) -> None:
        """Rotate through the plans already started, so going back to one
        you paused doesn't mean rebuilding it and losing its progress."""
        plans = self.plans.list_plans()
        if len(plans) < 2:
            self.notify("No other plan to switch to - press n to start one.")
            return
        ids = [p["id"] for p in plans]
        current = self._plan_id if self._plan_id in ids else ids[0]
        self.plans.set_active(ids[(ids.index(current) + 1) % len(ids)])
        self.mode = _TODAY
        self.showing_catch_up = False
        self._refresh()
