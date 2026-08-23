"""Testament/category scopes for browsing (the Books panel's `tab` filter)
and search alike. Pure over the real book rows - no widget, no reader.
"""

from __future__ import annotations

from bible_tui.services.book_scope_service import BOOK_SCOPES, breadcrumb, filter_books

# ----------------------------------------------------------------------
# BOOK_SCOPES itself
# ----------------------------------------------------------------------


def test_there_are_twelve_scopes():
    # Whole Bible + 2 testaments + 9 categories.
    assert len(BOOK_SCOPES) == 12


def test_every_scope_label_is_unique():
    labels = [scope.label for scope in BOOK_SCOPES]
    assert len(labels) == len(set(labels))


def test_the_first_scope_is_whole_bible_with_no_filter():
    whole = BOOK_SCOPES[0]
    assert whole.label == "Whole Bible"
    assert whole.testament is None
    assert whole.category is None


def test_every_category_in_the_canon_has_a_scope():
    # If a 67th book ever shows up with a new category, this fails loudly
    # instead of the new category silently having no way to filter to it.
    from bible_tui.models.book import CANONICAL_BOOKS

    categories_in_canon = {b.category for b in CANONICAL_BOOKS}
    categories_in_scopes = {s.category for s in BOOK_SCOPES if s.category}
    assert categories_in_canon == categories_in_scopes


# ----------------------------------------------------------------------
# filter_books
# ----------------------------------------------------------------------


def _scope(label):
    return next(s for s in BOOK_SCOPES if s.label == label)


def test_whole_bible_returns_every_book(repo):
    books = repo.get_all_books()
    assert len(filter_books(books, _scope("Whole Bible"))) == 66


def test_old_testament_is_thirty_nine_books(repo):
    books = repo.get_all_books()
    assert len(filter_books(books, _scope("Old Testament"))) == 39


def test_new_testament_is_twenty_seven_books(repo):
    books = repo.get_all_books()
    assert len(filter_books(books, _scope("New Testament"))) == 27


def test_gospels_is_exactly_matthew_mark_luke_john(repo):
    books = repo.get_all_books()
    names = {b["name"] for b in filter_books(books, _scope("Gospels"))}
    assert names == {"Matthew", "Mark", "Luke", "John"}


def test_category_counts_match_the_canon(repo):
    books = repo.get_all_books()
    expected = {
        "Law": 5,
        "History": 12,
        "Poetry": 5,
        "Major Prophets": 5,
        "Minor Prophets": 12,
        "Gospels": 4,
        "Acts": 1,
        "Epistles": 21,
        "Apocalyptic": 1,
    }
    for label, count in expected.items():
        assert len(filter_books(books, _scope(label))) == count, label


# ----------------------------------------------------------------------
# breadcrumb
# ----------------------------------------------------------------------


def test_breadcrumb_of_genesis(repo):
    genesis = repo.get_book(1)
    assert breadcrumb(genesis) == "OT · Law"


def test_breadcrumb_of_matthew(repo):
    matthew = repo.get_book(40)
    assert breadcrumb(matthew) == "NT · Gospels"
