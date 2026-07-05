"""Clipboard payload construction - pure text formatting, no I/O.

Kept apart from the reader screen so the exact output for a verse, a range,
and a whole chapter is unit-testable without standing up a terminal.
"""

from __future__ import annotations

from ..models.verse import Verse


def verse_payload(verse: Verse, translation_code: str) -> tuple[str, str]:
    """A single verse: ``John 3:16 - For God so loved… (KJV)``."""
    label = verse.reference
    return f"{label} - {verse.text} ({translation_code})", label


def range_payload(verses: list[Verse], translation_code: str) -> tuple[str, str]:
    """A contiguous run of verses, headed by the reference it spans."""
    if not verses:
        raise ValueError("range_payload needs at least one verse")
    if len(verses) == 1:
        return verse_payload(verses[0], translation_code)

    first, last = verses[0], verses[-1]
    label = f"{first.book_name} {first.chapter}:{first.verse}-{last.verse}"
    return _numbered_block(label, verses, translation_code), label


def chapter_payload(verses: list[Verse], translation_code: str) -> tuple[str, str]:
    """The whole chapter - what ``y`` copies in paragraph view."""
    if not verses:
        raise ValueError("chapter_payload needs at least one verse")
    first = verses[0]
    label = f"{first.book_name} {first.chapter}"
    return _numbered_block(label, verses, translation_code), label


def _numbered_block(label: str, verses: list[Verse], translation_code: str) -> str:
    lines = [f"{label} ({translation_code})"]
    lines.extend(f"{v.verse} {v.text}" for v in verses)
    return "\n".join(lines) + "\n"
