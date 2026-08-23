"""The alias table is what lets "Psalm", "jn" and "1cor" resolve when the
books table only stores "Psalms", "John" and "1 Corinthians"."""

from __future__ import annotations

import pytest

from bible_tui.data.book_aliases import normalise_book_query


@pytest.mark.parametrize(
    ("typed", "canonical"),
    [
        # Singular/plural and alternate titles.
        ("Psalm", "Psalms"),
        ("song of songs", "Song of Solomon"),
        ("Revelations", "Revelation"),
        # Short forms.
        ("ps", "Psalms"),
        ("jn", "John"),
        ("matt", "Matthew"),
        ("rev", "Revelation"),
        # Numbered books, in every ordinal spelling and spacing.
        ("1 cor", "1 Corinthians"),
        ("1cor", "1 Corinthians"),
        ("I Cor", "1 Corinthians"),
        ("ii sam", "2 Samuel"),
        ("3 john", "3 John"),
        ("iii jn", "3 John"),
    ],
)
def test_common_spellings_resolve_to_the_canonical_name(typed, canonical):
    assert normalise_book_query(typed) == canonical


def test_case_and_spacing_are_ignored():
    assert normalise_book_query("  1   COR  ") == "1 Corinthians"


def test_bare_john_stays_the_gospel_not_an_epistle():
    # The numbered-book stems are built from "john", so the unnumbered form
    # has to be re-pinned afterwards or 1-3 John would swallow the Gospel.
    assert normalise_book_query("John") == "John"
    assert normalise_book_query("jn") == "John"


def test_canonical_names_pass_through_untouched():
    assert normalise_book_query("Genesis") == "Genesis"


def test_unknown_input_is_returned_trimmed_for_the_caller_to_reject():
    assert normalise_book_query("  Geenesis ") == "Geenesis"
