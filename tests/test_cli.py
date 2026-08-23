"""Argument shaping for the command surface.

The command handlers themselves need a populated database, so they're
exercised end-to-end by the smoke tests; what's pinned here is the parsing
that decides *which* handler runs.
"""

from __future__ import annotations

import pytest

from bible_tui.cli import _build_parser, _normalise


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        # A bare reference is the form people type first; it means `read`.
        (["John 3:16"], ["read", "John 3:16"]),
        (["John 3:16", "-t", "ASV"], ["read", "John 3:16", "-t", "ASV"]),
        # Explicit subcommands are left alone.
        (["read", "John 3:16"], ["read", "John 3:16"]),
        (["search", "love"], ["search", "love"]),
        (["intro"], ["intro"]),
        # Nothing to rewrite.
        ([], []),
        (["--no-banner"], ["--no-banner"]),
    ],
)
def test_leading_positional_is_rewritten_to_read(argv, expected):
    assert _normalise(argv) == expected


def test_a_value_after_a_flag_is_never_mistaken_for_a_reference():
    # Rewriting a non-leading positional would turn `--banner` plus a flag
    # value into a bogus `read`.
    assert _normalise(["--banner"]) == ["--banner"]


def test_a_bible_url_dispatches_like_a_typed_reference():
    assert _normalise(["bible://John/3/16"]) == ["read", "John 3:16"]


def test_a_bible_url_with_trailing_flags_keeps_them():
    assert _normalise(["bible://John/3/16", "-t", "ASV"]) == ["read", "John 3:16", "-t", "ASV"]


def test_no_arguments_selects_the_tui():
    args = _build_parser().parse_args([])
    assert args.command is None
    assert args.banner is False and args.no_banner is False


def test_read_joins_a_multi_word_reference():
    args = _build_parser().parse_args(_normalise(["1 cor", "13:4-7"]))
    assert args.command == "read"
    assert " ".join(args.reference) == "1 cor 13:4-7"


def test_translation_flag_is_available_on_the_lookup_commands():
    for command in ("read", "search", "random", "today"):
        argv = [command, "x"] if command in ("read", "search") else [command]
        args = _build_parser().parse_args(argv + ["-t", "WEB"])
        assert args.translation == "WEB"


def test_banner_and_no_banner_are_mutually_intelligible_flags():
    assert _build_parser().parse_args(["--banner"]).banner is True
    assert _build_parser().parse_args(["--no-banner"]).no_banner is True


# ----------------------------------------------------------------------
# Backup, restore, check
# ----------------------------------------------------------------------


def test_backup_takes_an_optional_destination():
    bare = _build_parser().parse_args(["backup"])
    assert bare.command == "backup" and bare.path is None and bare.personal is False

    placed = _build_parser().parse_args(["backup", "/tmp/x.db"])
    assert placed.path == "/tmp/x.db"


def test_backup_can_be_narrowed_to_personal_data():
    args = _build_parser().parse_args(["backup", "--personal"])
    assert args.personal is True


def test_restore_requires_a_path():
    args = _build_parser().parse_args(["restore", "/tmp/x.db"])
    assert args.command == "restore" and args.path == "/tmp/x.db"
    assert args.replace is False

    with pytest.raises(SystemExit):
        _build_parser().parse_args(["restore"])


def test_restore_can_replace_instead_of_merging():
    assert _build_parser().parse_args(["restore", "x.json", "--replace"]).replace is True


def test_check_defaults_to_the_quick_pass():
    args = _build_parser().parse_args(["check"])
    assert args.command == "check" and args.thorough is False
    assert _build_parser().parse_args(["check", "--thorough"]).thorough is True


@pytest.mark.parametrize("command", ["backup", "restore", "check"])
def test_the_new_commands_are_not_mistaken_for_references(command):
    # Without registering them, `bible check` would try to read a book
    # called "check".
    assert _normalise([command, "x"])[0] == command


def test_profile_flag_is_available_before_and_after_a_subcommand():
    assert _build_parser().parse_args(["--profile", "work", "read", "John 3:16"]).profile == "work"


def test_profile_defaults_to_none_when_not_given():
    assert _build_parser().parse_args(["read", "John 3:16"]).profile is None
