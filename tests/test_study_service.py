from __future__ import annotations

import pytest

from bible_tui.models.study import StrongsEntry
from bible_tui.services.study_service import StudyService


@pytest.fixture
def study(repo):
    repo.conn.execute(
        "INSERT INTO strongs (code, language, transliteration, definition, pronunciation) "
        "VALUES ('G26', 'Greek', 'agape', 'love, benevolence', \"ag-ah'-pay\")"
    )
    repo.conn.commit()
    return StudyService(repo)


def test_search_strongs_returns_entries(study):
    results = study.search_strongs("agape")
    assert results == [StrongsEntry("G26", "Greek", "agape", "love, benevolence", "ag-ah'-pay")]


def test_search_strongs_with_a_blank_query_returns_nothing(study):
    # An empty dictionary search is a prompt for input, not "show everything".
    assert study.search_strongs("") == []
    assert study.search_strongs("   ") == []


def test_study_markers_for_chapter_delegates_to_the_repository(study):
    study.repo.conn.execute(
        "INSERT INTO cross_references (from_book_id, from_chapter, from_verse, to_book_id, to_chapter, to_verse) "
        "VALUES (43, 3, 16, 1, 1, 1)"
    )
    study.repo.conn.commit()
    assert study.study_markers_for_chapter(43, 3) == {16}
