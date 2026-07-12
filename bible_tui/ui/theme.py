"""Named colour themes, ported from christ-cli's palette set.

Each entry pairs a Textual ``Theme`` (which drives the built-in ``$primary``,
``$surface``… design tokens) with the extra tokens our own widgets read:
panel borders, the cursor row, and the search-match colour. Themes cycle in
list order with ``t``.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.theme import Theme


@dataclass(frozen=True)
class Palette:
    """A theme plus the extra tokens the reader's widgets style against."""

    name: str
    label: str
    theme: Theme


def _theme(
    *,
    name: str,
    dark: bool,
    bg: str,
    surface: str,
    panel: str,
    border: str,
    border_active: str,
    text: str,
    text_dim: str,
    text_muted: str,
    accent: str,
    accent_soft: str,
    highlight_bg: str,
    search_match: str,
) -> Theme:
    return Theme(
        name=name,
        dark=dark,
        background=bg,
        surface=surface,
        panel=panel,
        foreground=text,
        primary=accent_soft,
        secondary=accent,
        accent=accent,
        warning=search_match,
        error=search_match,
        success=accent_soft,
        variables={
            # Panel chrome: inactive panels recede, the focused one is bright.
            "border": border_active,
            "border-blurred": border,
            # Text ramp - three steps, same as the Rust theme struct.
            "text-muted": text_dim,
            "text-disabled": text_muted,
            "footer-key-foreground": accent_soft,
            "footer-description-foreground": text_dim,
            # Textual paints list/option cursors with these; left at their
            # defaults they resolve to $primary, which is a *light* tone in
            # every one of these palettes and washes the cursor row out.
            "block-cursor-background": highlight_bg,
            "block-cursor-foreground": accent,
            "block-cursor-text-style": "bold",
            "block-cursor-blurred-background": highlight_bg,
            "block-cursor-blurred-foreground": text,
            "block-cursor-blurred-text-style": "none",
            # Our widgets read these directly.
            "bible-cursor-bg": highlight_bg,
            "bible-cursor-fg": accent,
            "bible-search-match": search_match,
            "bible-verse-number": text_muted,
            "bible-dim": text_dim,
        },
    )


#: Slate - cool blue-gray dark theme (default).
SLATE = Palette(
    "slate",
    "Slate",
    _theme(
        name="slate",
        dark=True,
        bg="#0f172a",
        surface="#1e293b",
        panel="#1e293b",
        border="#475569",
        border_active="#e2e8f0",
        text="#f1f5f9",
        text_dim="#94a3b8",
        text_muted="#64748b",
        accent="#ffffff",
        accent_soft="#cbd5e1",
        highlight_bg="#37465f",
        search_match="#fbbf24",
    ),
)

#: Midnight - shadcn/Vercel style: pure black, neutral grays, sharp contrast.
MIDNIGHT = Palette(
    "midnight",
    "Midnight",
    _theme(
        name="midnight",
        dark=True,
        bg="#000000",
        surface="#0a0a0a",
        panel="#0a0a0a",
        border="#262626",
        border_active="#a3a3a3",
        text="#fafafa",
        text_dim="#737373",
        text_muted="#525252",
        accent="#ffffff",
        accent_soft="#d4d4d4",
        highlight_bg="#232323",
        search_match="#eab308",
    ),
)

#: Parchment - warm cream/sepia, built for long reading.
PARCHMENT = Palette(
    "parchment",
    "Parchment",
    _theme(
        name="parchment",
        dark=False,
        bg="#f5f0e1",
        surface="#ede6d3",
        panel="#ede6d3",
        border="#c4b599",
        border_active="#786446",
        text="#372f23",
        text_dim="#8c7d64",
        text_muted="#a89b84",
        accent="#282014",
        accent_soft="#64553c",
        highlight_bg="#d2c3a0",
        search_match="#b4641e",
    ),
)

#: Gospel - clean bright white, crisp and minimal.
GOSPEL = Palette(
    "gospel",
    "Gospel",
    _theme(
        name="gospel",
        dark=False,
        bg="#ffffff",
        surface="#f9fafb",
        panel="#f9fafb",
        border="#d1d5db",
        border_active="#374151",
        text="#111827",
        text_dim="#6b7280",
        text_muted="#9ca3af",
        accent="#000000",
        accent_soft="#4b5563",
        highlight_bg="#dce1eb",
        search_match="#d97706",
    ),
)


#: High Contrast - maximum separation for low vision. Pure black ground,
#: pure white text, and a saturated cursor that cannot be mistaken for
#: unselected text at any brightness.
HIGH_CONTRAST = Palette(
    "high-contrast",
    "High Contrast",
    _theme(
        name="high-contrast",
        dark=True,
        bg="#000000",
        surface="#000000",
        panel="#000000",
        border="#ffffff",
        border_active="#ffff00",
        text="#ffffff",
        text_dim="#e0e0e0",
        text_muted="#c8c8c8",
        accent="#ffff00",
        accent_soft="#ffffff",
        highlight_bg="#0000cc",
        search_match="#ffff00",
    ),
)

#: Daylight - a high-contrast light counterpart, for bright rooms and for
#: anyone who finds white-on-black harder rather than easier.
DAYLIGHT = Palette(
    "daylight",
    "Daylight",
    _theme(
        name="daylight",
        dark=False,
        bg="#ffffff",
        surface="#ffffff",
        panel="#ffffff",
        border="#000000",
        border_active="#0000aa",
        text="#000000",
        text_dim="#2b2b2b",
        text_muted="#454545",
        accent="#0000aa",
        accent_soft="#000000",
        highlight_bg="#ffe680",
        search_match="#aa0000",
    ),
)

#: Accessible - colour-vision-safe. Red/green carry no meaning anywhere in
#: this palette; the blue/orange pair stays distinguishable under
#: deuteranopia, protanopia and tritanopia alike.
ACCESSIBLE = Palette(
    "accessible",
    "Accessible",
    _theme(
        name="accessible",
        dark=True,
        bg="#10151c",
        surface="#18202b",
        panel="#18202b",
        border="#4c6178",
        border_active="#7fbfff",
        text="#eef3f8",
        text_dim="#9db2c6",
        text_muted="#71889e",
        accent="#7fbfff",
        accent_soft="#cfe4f7",
        highlight_bg="#2d4763",
        search_match="#ffab40",
    ),
)

#: Terminal - leans on the emulator's own colours via the ANSI palette.
TERMINAL = Palette(
    "terminal",
    "Terminal",
    Theme(
        name="terminal",
        dark=True,
        background="ansi_default",
        surface="ansi_default",
        panel="ansi_default",
        foreground="ansi_default",
        primary="ansi_bright_white",
        secondary="ansi_bright_white",
        accent="ansi_bright_white",
        warning="ansi_yellow",
        error="ansi_red",
        success="ansi_green",
        ansi=True,
        variables={
            "border": "ansi_bright_white",
            "border-blurred": "ansi_blue",
            "text-muted": "ansi_bright_black",
            "text-disabled": "ansi_bright_black",
            "block-cursor-background": "ansi_blue",
            "block-cursor-foreground": "ansi_bright_white",
            "block-cursor-text-style": "bold",
            "block-cursor-blurred-background": "ansi_blue",
            "block-cursor-blurred-foreground": "ansi_bright_white",
            "block-cursor-blurred-text-style": "none",
            "bible-cursor-bg": "ansi_blue",
            "bible-cursor-fg": "ansi_bright_white",
            "bible-search-match": "ansi_yellow",
            "bible-verse-number": "ansi_bright_black",
            "bible-dim": "ansi_bright_black",
            # Textual's own built-in ansi-dark theme sets these explicitly
            # rather than relying on design.py's usual "transparent" default
            # (that default is skipped whenever ansi=True) - every ansi
            # theme has to provide them itself, or CSS that references them
            # (Screen's own inline-mode border, several core widgets) fails
            # to parse the moment this theme is actually selected.
            "ansi-background": "ansi_black",
            "ansi-foreground": "ansi_bright_white",
            "input-cursor-background": "ansi_blue",
            "input-cursor-foreground": "ansi_bright_white",
            "input-selection-background": "ansi_blue",
            "input-selection-foreground": "ansi_bright_white",
            "screen-selection-background": "ansi_blue",
            "screen-selection-foreground": "ansi_bright_white",
        },
    ),
)

#: Cycle order for the ``t`` keybinding. The four reading palettes come
#: first, then the accessibility ones, then Terminal - so cycling for looks
#: doesn't wander through the accessibility themes on the way.
PALETTES: list[Palette] = [
    SLATE,
    MIDNIGHT,
    PARCHMENT,
    GOSPEL,
    HIGH_CONTRAST,
    DAYLIGHT,
    ACCESSIBLE,
    TERMINAL,
]

#: What automatic night mode switches between, and the hours it calls night.
#: A reader who has chosen a light or an accessibility theme is left alone -
#: only these two participate.
NIGHT_THEME = MIDNIGHT.name
DAY_THEME = PARCHMENT.name
NIGHT_STARTS_HOUR = 19
NIGHT_ENDS_HOUR = 7


def theme_for_hour(hour: int) -> str:
    """Which theme automatic night mode wants at `hour` (0-23)."""
    is_night = hour >= NIGHT_STARTS_HOUR or hour < NIGHT_ENDS_HOUR
    return NIGHT_THEME if is_night else DAY_THEME

PALETTES_BY_NAME: dict[str, Palette] = {p.name: p for p in PALETTES}

DEFAULT_THEME = SLATE.name


def next_theme(name: str) -> str:
    """The next theme in cycle order, wrapping around. Unknown names restart
    the cycle rather than raising - a stale config shouldn't break launch."""
    try:
        index = PALETTES.index(PALETTES_BY_NAME[name])
    except KeyError:
        return PALETTES[0].name
    return PALETTES[(index + 1) % len(PALETTES)].name


def label_for(name: str) -> str:
    palette = PALETTES_BY_NAME.get(name)
    return palette.label if palette else name


#: Fallbacks for the variables our widgets reference.
#:
#: Textual fails CSS parsing outright if a ``$variable`` is defined neither by
#: the active theme nor here, and the app's stylesheet is parsed while the
#: built-in default theme is still current - so every custom token needs an
#: entry, expressed in terms of built-in tokens.
THEME_VARIABLE_DEFAULTS: dict[str, str] = {
    "bible-cursor-bg": "$primary 30%",
    "bible-cursor-fg": "$foreground",
    "bible-search-match": "$warning",
    "bible-verse-number": "$text-disabled",
    "bible-dim": "$text-muted",
}


def rich_color(app, token: str, fallback: str = "default") -> str:
    """Resolve a theme variable to something Rich can style a span with.

    Textual's own content markup mis-measures styled spans when the text
    wraps - it opens a gap at every span boundary - so anything that both
    wraps *and* styles part of a line is built as a ``rich.text.Text``
    instead. Rich needs a concrete colour rather than a ``$token``, which is
    what this converts.
    """
    value = (getattr(app, "theme_variables", None) or {}).get(token)
    if not value:
        return fallback
    if value.startswith("ansi_"):
        # "ansi_bright_black" -> "bright_black", which Rich knows by name.
        return value[len("ansi_") :]
    return value
