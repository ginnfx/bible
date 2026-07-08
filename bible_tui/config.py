from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from .ui.theme import DEFAULT_THEME, PALETTES_BY_NAME

CONFIG_DIR = Path.home() / ".config" / "bible-tui"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
DEFAULT_DB_PATH = CONFIG_DIR / "bible.db"

#: Multiple profiles ("multiple user profiles on one device") are separate
#: config/db file pairs, not rows in one shared database - simplest thing
#: that works, and it means a profile is just a directory. The default
#: profile keeps living directly under CONFIG_DIR rather than under its own
#: `profiles/default/` subdirectory, so nobody's existing install moves.
DEFAULT_PROFILE = "default"
PROFILE_ENV_VAR = "BIBLE_TUI_PROFILE"


def config_dir_for(profile: str | None) -> Path:
    if not profile or profile == DEFAULT_PROFILE:
        return CONFIG_DIR
    return CONFIG_DIR / "profiles" / profile

#: Panel identifiers persisted in ``active_panel``.
PANEL_BOOKS = "books"
PANEL_CHAPTERS = "chapters"
PANEL_SCRIPTURE = "scripture"
PANELS = (PANEL_BOOKS, PANEL_CHAPTERS, PANEL_SCRIPTURE)

#: Scripture rendering modes persisted in ``view_mode``.
VIEW_VERSE_PER_LINE = "verses"
VIEW_PARAGRAPH = "paragraph"
VIEW_MODES = (VIEW_VERSE_PER_LINE, VIEW_PARAGRAPH)

#: Line-wrap modes persisted in ``line_wrap``.
WRAP_SOFT = "soft"
WRAP_HARD = "hard"
WRAP_NONE = "none"
WRAP_MODES = (WRAP_SOFT, WRAP_HARD, WRAP_NONE)

#: Verse-spacing levels persisted in ``verse_spacing`` - Textual has no
#: line-height property, so "more breathing room" is delivered as margin
#: between verse rows instead.
SPACING_COMPACT = "compact"
SPACING_COMFORTABLE = "comfortable"
SPACING_SPACIOUS = "spacious"
SPACING_LEVELS = (SPACING_COMPACT, SPACING_COMFORTABLE, SPACING_SPACIOUS)
#: margin-bottom for each spacing level, in cells.
SPACING_MARGINS = {SPACING_COMPACT: 0, SPACING_COMFORTABLE: 1, SPACING_SPACIOUS: 2}


@dataclass
class Config:
    """Persisted preferences *and* session state.

    Reading position lives in the database (it is user data alongside
    bookmarks and notes); everything that describes how the app should look
    and which panel you left focused lives here, so a fresh launch drops you
    back exactly where you were.
    """

    db_path: Path = field(default_factory=lambda: DEFAULT_DB_PATH)
    translation_code: str = "KJV"
    theme: str = DEFAULT_THEME
    view_mode: str = VIEW_VERSE_PER_LINE
    active_panel: str = PANEL_SCRIPTURE
    #: Verse *number* the cursor was on, not a list index - translations
    #: number verses differently, so an index wouldn't survive a switch.
    selected_verse: int = 0
    #: The intro animation plays on the first launch only; `bible intro`
    #: replays it on demand.
    banner_shown: bool = False
    #: When on, the theme follows the clock (see ui.theme.theme_for_hour)
    #: instead of whatever was last chosen with `t`.
    auto_night_mode: bool = False
    last_position: tuple[int, int] | None = None  # (book_id, chapter)
    #: Which profile this config was loaded from / saves back to - see
    #: config_dir_for(). Not user-facing preference data, just routing.
    profile: str = DEFAULT_PROFILE
    #: The first-run wizard (translation + theme) runs once per profile,
    #: separately from the intro banner.
    wizard_shown: bool = False
    #: Appearance settings - see the WRAP_*/SPACING_* constants above.
    line_wrap: str = WRAP_SOFT
    verse_spacing: str = SPACING_COMFORTABLE
    #: One toggle standing in for "adjust font size"/"choose a font", which
    #: Textual has no CSS property for at all: forces a high-contrast
    #: palette, spacious verse padding, and a thicker cursor row instead.
    low_vision: bool = False
    show_chapter_heading: bool = True
    #: 1 or 2. Two splits the scripture panel into side-by-side columns,
    #: same CSS-grid mechanism as the three-panel Books/Chapters/Scripture
    #: layout, one level deeper.
    scripture_columns: int = 1

    @classmethod
    def load(cls, profile: str | None = None) -> "Config":
        profile = profile or DEFAULT_PROFILE
        config_dir = config_dir_for(profile)
        config_path = config_dir / "config.yaml"
        default_db = config_dir / "bible.db"
        if not config_path.exists():
            return cls(profile=profile, db_path=default_db)
        try:
            raw = yaml.safe_load(config_path.read_text()) or {}
        except (OSError, yaml.YAMLError):
            # A corrupt or unreadable config must not block launch; defaults
            # are always valid and the next save rewrites the file.
            return cls(profile=profile, db_path=default_db)
        if not isinstance(raw, dict):
            return cls(profile=profile, db_path=default_db)

        last_position = raw.get("last_position")
        return cls(
            profile=profile,
            db_path=Path(raw.get("db_path") or default_db).expanduser(),
            translation_code=raw.get("translation_code") or "KJV",
            theme=_one_of(raw.get("theme"), PALETTES_BY_NAME, DEFAULT_THEME),
            view_mode=_one_of(raw.get("view_mode"), VIEW_MODES, VIEW_VERSE_PER_LINE),
            active_panel=_one_of(raw.get("active_panel"), PANELS, PANEL_SCRIPTURE),
            selected_verse=max(0, _as_int(raw.get("selected_verse"))),
            banner_shown=bool(raw.get("banner_shown", False)),
            auto_night_mode=bool(raw.get("auto_night_mode", False)),
            last_position=tuple(last_position) if last_position else None,
            wizard_shown=bool(raw.get("wizard_shown", False)),
            line_wrap=_one_of(raw.get("line_wrap"), WRAP_MODES, WRAP_SOFT),
            verse_spacing=_one_of(raw.get("verse_spacing"), SPACING_LEVELS, SPACING_COMFORTABLE),
            low_vision=bool(raw.get("low_vision", False)),
            show_chapter_heading=bool(raw.get("show_chapter_heading", True)),
            scripture_columns=2 if _as_int(raw.get("scripture_columns")) == 2 else 1,
        )

    def save(self) -> None:
        config_dir = config_dir_for(self.profile)
        config_dir.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data["db_path"] = str(self.db_path)
        data["last_position"] = list(self.last_position) if self.last_position else None
        (config_dir / "config.yaml").write_text(yaml.safe_dump(data, sort_keys=False))


def _one_of(value: object, allowed, fallback: str) -> str:
    """Values written by a newer build (or hand-edited) fall back to the
    default instead of propagating an unknown token into the UI."""
    return value if isinstance(value, str) and value in allowed else fallback


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
