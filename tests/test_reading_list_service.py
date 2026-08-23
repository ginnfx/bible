from __future__ import annotations

import pytest

from bible_tui.services.reading_list_service import ReadingListService


@pytest.fixture
def lists(repo):
    return ReadingListService(repo)


def test_a_new_list_starts_empty(lists):
    list_id = lists.create_list("Christmas readings")
    assert lists.items(list_id) == []


def test_created_lists_are_listed_by_name(lists):
    lists.create_list("Christmas readings")
    lists.create_list("Advent")
    assert [r["name"] for r in lists.list_lists()] == ["Advent", "Christmas readings"]


def test_adding_a_verse_to_a_list(lists):
    list_id = lists.create_list("Christmas readings")
    lists.add_verse(list_id, 43, 3, 16)
    items = lists.items(list_id)
    assert len(items) == 1
    assert items[0]["book_name"] == "John"
    assert (items[0]["chapter"], items[0]["verse"]) == (3, 16)


def test_removing_an_item_from_a_list(lists):
    list_id = lists.create_list("Christmas readings")
    item_id = lists.add_verse(list_id, 43, 3, 16)
    lists.remove_item(item_id)
    assert lists.items(list_id) == []


def test_deleting_a_list_removes_its_items(lists):
    list_id = lists.create_list("Christmas readings")
    lists.add_verse(list_id, 43, 3, 16)
    lists.delete_list(list_id)
    assert lists.list_lists() == []


def test_renaming_a_list(lists):
    list_id = lists.create_list("Advent")
    lists.rename_list(list_id, "Advent 2026")
    assert [r["name"] for r in lists.list_lists()] == ["Advent 2026"]


def test_lists_are_independent_of_each_other(lists):
    a = lists.create_list("A")
    b = lists.create_list("B")
    lists.add_verse(a, 1, 1, 1)
    assert lists.items(a) != []
    assert lists.items(b) == []
