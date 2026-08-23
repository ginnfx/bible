"""The two drawing helpers behind the stats screen.

Both are pure functions over numbers, which is the whole reason they were
pulled out of the render methods - a bar that rounds a started book down to
nothing is a real bug and shouldn't need a running app to catch.
"""

from __future__ import annotations

import pytest

from bible_tui.ui.screens.stats import _parse_goal, bar, sparkline


def test_an_empty_bar_is_all_empty():
    assert bar(0.0, 10) == "░" * 10


def test_a_full_bar_is_all_full():
    assert bar(1.0, 10) == "█" * 10


def test_a_half_bar_is_half_full():
    assert bar(0.5, 10) == "█████░░░░░"


def test_a_bar_is_always_its_full_width(size=17):
    for fraction in (0.0, 0.01, 0.33, 0.5, 0.99, 1.0):
        assert len(bar(fraction, size)) == size


def test_barely_started_still_shows_something():
    # Rounding a started book down to an empty bar would tell the reader
    # they haven't touched it.
    assert bar(0.01, 20).startswith("█")


def test_out_of_range_fractions_are_clamped():
    assert bar(-5, 8) == "░" * 8
    assert bar(9, 8) == "█" * 8


def test_a_sparkline_has_one_cell_per_day():
    assert len(sparkline([0, 1, 2, 3])) == 4


def test_a_quiet_month_still_shows_its_full_width():
    # Drawing nothing would make a thirty-day chart look like no chart.
    assert sparkline([0, 0, 0]) == "···"


def test_the_busiest_day_is_the_tallest():
    line = sparkline([1, 5, 2])
    assert line[1] == "█"
    assert line[0] != "█" and line[2] != "█"


def test_a_read_day_is_never_drawn_as_a_gap():
    # One chapter against a busy day still has to read as reading.
    assert sparkline([1, 100])[0] not in ("·", " ")


def test_an_empty_history_draws_nothing():
    assert sparkline([]) == ""


@pytest.mark.parametrize("counts", [[3], [0, 7, 7, 0], [1, 2, 3, 4, 5, 6, 7, 8, 9]])
def test_every_cell_comes_from_the_ramp(counts):
    assert set(sparkline(counts)) <= set("·▁▂▃▄▅▆▇█")


# ----------------------------------------------------------------------
# Chart axis
# ----------------------------------------------------------------------


import datetime as dt  # noqa: E402

from bible_tui.ui.screens.stats import axis  # noqa: E402

FIRST = dt.date(2026, 7, 29)
LAST = dt.date(2026, 8, 27)


def test_the_axis_is_exactly_as_wide_as_the_chart():
    for width in (14, 20, 30, 60):
        assert len(axis(FIRST, LAST, width)) == width


def test_the_last_label_ends_at_the_last_cell():
    # Otherwise the right-hand date points at a day in the middle of the
    # chart, which is worse than no label at all.
    assert axis(FIRST, LAST, 30).endswith("Aug 27")
    assert axis(FIRST, LAST, 30).startswith("Jul 29")


def test_a_narrow_chart_keeps_the_newest_date():
    # Two dates don't fit; the one that anchors "now" is the one to keep.
    assert axis(FIRST, LAST, 8) == "  Aug 27"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("20 minutes", ("minutes", 20)),
        ("20m", ("minutes", 20)),
        ("20", ("minutes", 20)),
        ("3 chapters", ("chapters", 3)),
        ("3c", ("chapters", 3)),
        ("  5 CHAPTERS  ", ("chapters", 5)),
    ],
)
def test_parsing_a_readable_goal(text, expected):
    assert _parse_goal(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "zero chapters", "0", "-5", "chapters"])
def test_parsing_an_unreadable_goal_returns_none(text):
    assert _parse_goal(text) is None
