"""Exact clipboard payloads for a verse, a range, and a chapter."""

from __future__ import annotations

import pytest

from bible_tui.models.verse import Verse
from bible_tui.services import copy_service


def verse(number: int, text: str) -> Verse:
    return Verse(id=number, book_id=43, book_name="John", chapter=3, verse=number, text=text)


JOHN_3 = [
    verse(16, "For God so loved the world"),
    verse(17, "For God sent not his Son"),
    verse(18, "He that believeth on him"),
]


def test_single_verse_is_one_line_with_the_translation():
    text, label = copy_service.verse_payload(JOHN_3[0], "KJV")
    assert label == "John 3:16"
    assert text == "John 3:16 - For God so loved the world (KJV)"


def test_range_is_headed_by_the_span_then_numbered_lines():
    text, label = copy_service.range_payload(JOHN_3, "KJV")
    assert label == "John 3:16-18"
    assert text == (
        "John 3:16-18 (KJV)\n"
        "16 For God so loved the world\n"
        "17 For God sent not his Son\n"
        "18 He that believeth on him\n"
    )


def test_a_one_verse_range_degrades_to_the_single_verse_form():
    # Pressing Y and copying without moving shouldn't produce a "range" of one.
    assert copy_service.range_payload(JOHN_3[:1], "KJV") == copy_service.verse_payload(
        JOHN_3[0], "KJV"
    )


def test_chapter_payload_is_labelled_without_a_verse_number():
    text, label = copy_service.chapter_payload(JOHN_3, "ASV")
    assert label == "John 3"
    assert text.startswith("John 3 (ASV)\n16 For God so loved")


@pytest.mark.parametrize("builder", [copy_service.range_payload, copy_service.chapter_payload])
def test_empty_selections_are_rejected_rather_than_copied_blank(builder):
    with pytest.raises(ValueError):
        builder([], "KJV")
