"""Theme cycling and the variable contract the widgets rely on."""

from __future__ import annotations

import pytest

from bible_tui.ui import theme

#: Every token our widgets reference with $... in CSS or via rich_color.
REQUIRED_VARIABLES = {
    "border",
    "border-blurred",
    "text-muted",
    "text-disabled",
    "block-cursor-background",
    "block-cursor-foreground",
    "bible-cursor-bg",
    "bible-cursor-fg",
    "bible-search-match",
    "bible-verse-number",
    "bible-dim",
}


def test_cycle_visits_every_theme_and_wraps():
    seen = [theme.PALETTES[0].name]
    for _ in range(len(theme.PALETTES) - 1):
        seen.append(theme.next_theme(seen[-1]))
    assert seen == [p.name for p in theme.PALETTES]
    assert theme.next_theme(seen[-1]) == theme.PALETTES[0].name


def test_an_unknown_saved_theme_restarts_the_cycle_rather_than_raising():
    # A config written by a newer build shouldn't stop the app from starting.
    assert theme.next_theme("no-such-theme") == theme.PALETTES[0].name


@pytest.mark.parametrize("palette", theme.PALETTES, ids=lambda p: p.name)
def test_every_palette_defines_every_variable_the_widgets_use(palette):
    missing = REQUIRED_VARIABLES - set(palette.theme.variables)
    assert not missing, f"{palette.name} is missing {sorted(missing)}"


def test_defaults_cover_the_custom_tokens_so_css_parses_before_a_theme_is_set():
    custom = {name for name in REQUIRED_VARIABLES if name.startswith("bible-")}
    assert custom <= set(theme.THEME_VARIABLE_DEFAULTS)


def test_label_falls_back_to_the_raw_name_for_unknown_themes():
    assert theme.label_for("slate") == "Slate"
    assert theme.label_for("mystery") == "mystery"


class _FakeApp:
    def __init__(self, variables):
        self.theme_variables = variables


def test_rich_color_strips_the_ansi_prefix_rich_does_not_understand():
    assert theme.rich_color(_FakeApp({"x": "ansi_bright_black"}), "x") == "bright_black"


def test_rich_color_passes_hex_through_and_falls_back_when_absent():
    assert theme.rich_color(_FakeApp({"x": "#ff0000"}), "x") == "#ff0000"
    assert theme.rich_color(_FakeApp({}), "x", "dim") == "dim"
    assert theme.rich_color(_FakeApp(None), "x", "dim") == "dim"


def test_accessibility_themes_are_available():
    names = {p.name for p in theme.PALETTES}
    assert {"high-contrast", "daylight", "accessible"} <= names


def test_night_mode_picks_dark_after_dusk_and_light_by_day():
    assert theme.theme_for_hour(23) == theme.NIGHT_THEME
    assert theme.theme_for_hour(3) == theme.NIGHT_THEME
    assert theme.theme_for_hour(6) == theme.NIGHT_THEME
    assert theme.theme_for_hour(7) == theme.DAY_THEME
    assert theme.theme_for_hour(12) == theme.DAY_THEME
    assert theme.theme_for_hour(18) == theme.DAY_THEME
    assert theme.theme_for_hour(19) == theme.NIGHT_THEME


def test_the_reading_themes_come_before_the_accessibility_ones():
    # Cycling with `t` should not wander through High Contrast on the way
    # from Gospel back to Slate.
    names = [p.name for p in theme.PALETTES]
    assert names[:4] == ["slate", "midnight", "parchment", "gospel"]
