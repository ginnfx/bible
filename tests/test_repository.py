"""Repository methods with no home in a more specific test file yet."""

from __future__ import annotations

import pytest


@pytest.fixture
def strongs_repo(repo):
    repo.conn.executemany(
        "INSERT INTO strongs (code, language, transliteration, definition, pronunciation) VALUES (?, ?, ?, ?, ?)",
        [
            ("H157", "Hebrew", "ahab", "to love, love", "aw-hab'"),
            ("G26", "Greek", "agape", "love, benevolence", "ag-ah'-pay"),
            ("G4102", "Greek", "pistis", "faith, belief, trust", "pis'-tis"),
        ],
    )
    repo.conn.commit()
    return repo


def test_searching_by_code(strongs_repo):
    rows = strongs_repo.search_strongs("G26")
    assert [r["code"] for r in rows] == ["G26"]


def test_searching_by_transliteration(strongs_repo):
    rows = strongs_repo.search_strongs("agape")
    assert [r["code"] for r in rows] == ["G26"]


def test_searching_by_definition_word_matches_multiple(strongs_repo):
    rows = strongs_repo.search_strongs("love")
    assert {r["code"] for r in rows} == {"H157", "G26"}


def test_a_search_with_no_matches_is_empty(strongs_repo):
    assert strongs_repo.search_strongs("xyzzy") == []


def test_search_is_case_insensitive(strongs_repo):
    rows = strongs_repo.search_strongs("FAITH")
    assert [r["code"] for r in rows] == ["G4102"]


# ----------------------------------------------------------------------
# Study markers (cross-references / commentary) for a chapter
# ----------------------------------------------------------------------


def test_a_chapter_with_no_study_content_has_no_markers(repo):
    assert repo.study_markers_for_chapter(43, 3) == set()


def test_a_cross_reference_marks_its_verse(repo):
    repo.conn.execute(
        "INSERT INTO cross_references (from_book_id, from_chapter, from_verse, to_book_id, to_chapter, to_verse) "
        "VALUES (43, 3, 16, 1, 1, 1)"
    )
    repo.conn.commit()
    assert repo.study_markers_for_chapter(43, 3) == {16}


def test_a_commentary_range_marks_every_verse_in_it(repo):
    repo.conn.execute(
        "INSERT INTO commentaries (book_id, chapter, verse_start, verse_end, author, text) "
        "VALUES (43, 3, 16, 18, 'Matthew Henry', 'On the love of God.')"
    )
    repo.conn.commit()
    assert repo.study_markers_for_chapter(43, 3) == {16, 17, 18}


def test_markers_are_scoped_to_the_requested_chapter(repo):
    repo.conn.execute(
        "INSERT INTO cross_references (from_book_id, from_chapter, from_verse, to_book_id, to_chapter, to_verse) "
        "VALUES (43, 3, 16, 1, 1, 1)"
    )
    repo.conn.commit()
    assert repo.study_markers_for_chapter(43, 17) == set()
