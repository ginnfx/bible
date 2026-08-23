from __future__ import annotations

import sqlite3

import pytest

from bible_tui.data.database import init_schema
from bible_tui.data.repository import BibleRepository
from bible_tui.models.book import CANONICAL_BOOKS


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_schema(connection)

    connection.executemany(
        """
        INSERT INTO books (id, book_num, name, abbreviation, osis_code, testament, category, chapter_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (b.book_num, b.book_num, b.name, b.abbreviation, b.osis_code, b.testament, b.category, b.chapter_count)
            for b in CANONICAL_BOOKS
        ],
    )
    connection.execute("INSERT INTO translations (code, name, year) VALUES ('KJV', 'King James Version', 1769)")
    translation_id = connection.execute("SELECT id FROM translations WHERE code = 'KJV'").fetchone()[0]

    # Seed a handful of known verses: all of Genesis 1 (50 verses is overkill;
    # a few plus the last verse of the book matter for chapter-rollover
    # tests), a couple of John verses, and Genesis 2:1 for next-chapter tests.
    seed_verses = [
        (1, 1, 1, "In the beginning God created the heaven and the earth."),
        (1, 1, 2, "And the earth was without form, and void."),
        (1, 1, 3, "And God said, Let there be light: and there was light."),
        (1, 2, 1, "Thus the heavens and the earth were finished."),
        (1, 50, 26, "So Joseph died, being an hundred and ten years old."),
        (43, 3, 16, "For God so loved the world, that he gave his only begotten Son."),
        (43, 3, 17, "For God sent not his Son into the world to condemn the world."),
        (66, 22, 21, "The grace of our Lord Jesus Christ be with you all. Amen."),
    ]
    connection.executemany(
        "INSERT INTO verses (translation_id, book_id, chapter, verse, text) VALUES (?, ?, ?, ?, ?)",
        [(translation_id, *v) for v in seed_verses],
    )
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture
def repo(conn):
    return BibleRepository(conn)
