"""Session state round-trips, and tolerates files it didn't write."""

from __future__ import annotations

import pytest

import bible_tui.config as config_module
from bible_tui.config import (
    PANEL_BOOKS,
    VIEW_PARAGRAPH,
    Config,
)


@pytest.fixture(autouse=True)
def config_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "config.yaml")
    return tmp_path / "config.yaml"


def test_a_missing_config_yields_usable_defaults():
    config = Config.load()
    assert config.theme == "slate"
    assert config.view_mode == "verses"
    assert config.banner_shown is False


def test_the_whole_session_round_trips(config_in_tmp):
    saved = Config(
        theme="parchment",
        view_mode=VIEW_PARAGRAPH,
        active_panel=PANEL_BOOKS,
        selected_verse=12,
        translation_code="ASV",
        banner_shown=True,
    )
    saved.save()

    loaded = Config.load()
    assert loaded.theme == "parchment"
    assert loaded.view_mode == VIEW_PARAGRAPH
    assert loaded.active_panel == PANEL_BOOKS
    assert loaded.selected_verse == 12
    assert loaded.translation_code == "ASV"
    assert loaded.banner_shown is True


def test_unknown_enum_values_fall_back_instead_of_reaching_the_ui(config_in_tmp):
    config_in_tmp.write_text("theme: neon\nview_mode: hologram\nactive_panel: sidebar\n")
    loaded = Config.load()
    assert (loaded.theme, loaded.view_mode, loaded.active_panel) == (
        "slate",
        "verses",
        "scripture",
    )


def test_a_corrupt_config_does_not_block_launch(config_in_tmp):
    config_in_tmp.write_text("{{{ not yaml")
    assert Config.load().theme == "slate"


def test_a_non_mapping_config_does_not_block_launch(config_in_tmp):
    config_in_tmp.write_text("- just\n- a list\n")
    assert Config.load().theme == "slate"


def test_a_garbage_verse_index_is_clamped_rather_than_crashing(config_in_tmp):
    config_in_tmp.write_text("selected_verse: not-a-number\n")
    assert Config.load().selected_verse == 0
    config_in_tmp.write_text("selected_verse: -5\n")
    assert Config.load().selected_verse == 0


# --- Profiles ---


def test_the_default_profile_is_unaffected_by_naming_it_explicitly(config_in_tmp):
    Config(theme="parchment").save()
    assert Config.load("default").theme == "parchment"
    assert Config.load().theme == "parchment"


def test_a_named_profile_gets_its_own_directory_under_config_dir(config_in_tmp):
    saved = Config.load("work")
    saved.theme = "midnight"
    saved.save()
    assert (config_in_tmp.parent / "profiles" / "work" / "config.yaml").exists()
    # And the default profile's file is untouched.
    assert not config_in_tmp.exists()


def test_two_profiles_do_not_see_each_others_settings(config_in_tmp):
    default_cfg = Config.load()
    default_cfg.theme = "gospel"
    default_cfg.save()

    work_cfg = Config.load("work")
    work_cfg.theme = "midnight"
    work_cfg.save()

    assert Config.load().theme == "gospel"
    assert Config.load("work").theme == "midnight"


def test_a_profiles_default_database_lives_alongside_its_own_config(config_in_tmp):
    cfg = Config.load("work")
    assert cfg.db_path == config_in_tmp.parent / "profiles" / "work" / "bible.db"


# --- Appearance ---


def test_appearance_defaults(config_in_tmp):
    config = Config.load()
    assert config.line_wrap == "soft"
    assert config.verse_spacing == "comfortable"
    assert config.low_vision is False
    assert config.show_chapter_heading is True
    assert config.scripture_columns == 1


def test_appearance_settings_round_trip(config_in_tmp):
    saved = Config(
        line_wrap="hard",
        verse_spacing="spacious",
        low_vision=True,
        show_chapter_heading=False,
        scripture_columns=2,
    )
    saved.save()

    loaded = Config.load()
    assert loaded.line_wrap == "hard"
    assert loaded.verse_spacing == "spacious"
    assert loaded.low_vision is True
    assert loaded.show_chapter_heading is False
    assert loaded.scripture_columns == 2


def test_an_unknown_wrap_or_spacing_value_falls_back(config_in_tmp):
    config_in_tmp.write_text("line_wrap: teleport\nverse_spacing: enormous\nscripture_columns: 7\n")
    loaded = Config.load()
    assert loaded.line_wrap == "soft"
    assert loaded.verse_spacing == "comfortable"
    assert loaded.scripture_columns == 1
