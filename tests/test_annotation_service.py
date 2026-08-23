import pytest

from bible_tui.services.annotation_service import AnnotationService


@pytest.fixture
def annotations(repo):
    return AnnotationService(repo)


def test_toggle_bookmark_adds_then_removes(repo):
    ann = AnnotationService(repo)
    assert ann.is_bookmarked(1, 1, 1) is False

    assert ann.toggle_bookmark(1, 1, 1) is True
    assert ann.is_bookmarked(1, 1, 1) is True

    assert ann.toggle_bookmark(1, 1, 1) is False
    assert ann.is_bookmarked(1, 1, 1) is False


def test_bookmark_keyed_by_verse_address_not_translation(repo):
    # Bookmarks key off (book_id, chapter, verse), not a translation-scoped
    # verse row, so a lookup doesn't need to know which translation was
    # active when the bookmark was made. This is the deliberate deviation
    # from the plan's original verse_id FK design (see schema.sql).
    ann = AnnotationService(repo)
    ann.toggle_bookmark(1, 1, 1)
    assert ann.is_bookmarked(1, 1, 1) is True


def test_add_and_retrieve_note(repo):
    ann = AnnotationService(repo)
    ann.add_note(1, 1, 1, "In the beginning...")
    notes = ann.get_notes(1, 1, 1)
    assert len(notes) == 1
    assert notes[0]["body"] == "In the beginning..."


def test_update_note(repo):
    ann = AnnotationService(repo)
    note_id = ann.add_note(1, 1, 1, "first draft")
    ann.update_note(note_id, "revised")
    notes = ann.get_notes(1, 1, 1)
    assert notes[0]["body"] == "revised"


def test_cycle_highlight_advances_through_colors_then_clears(repo):
    ann = AnnotationService(repo)
    assert ann.cycle_highlight(1, 1, 1) == "yellow"
    assert ann.cycle_highlight(1, 1, 1) == "green"
    assert ann.cycle_highlight(1, 1, 1) == "blue"
    assert ann.cycle_highlight(1, 1, 1) == "pink"
    assert ann.cycle_highlight(1, 1, 1) is None  # cleared
    assert ann.highlights_for_chapter(1, 1) == {}


def test_bookmarks_for_chapter_returns_only_that_chapter(repo):
    ann = AnnotationService(repo)
    ann.toggle_bookmark(1, 1, 1)
    ann.toggle_bookmark(1, 1, 3)
    ann.toggle_bookmark(1, 2, 1)
    assert ann.bookmarks_for_chapter(1, 1) == {1, 3}


# ----------------------------------------------------------------------
# Bookmark labels, ordering and filtering
# ----------------------------------------------------------------------


from bible_tui.data.repository import ORDER_CANONICAL  # noqa: E402


def test_a_new_bookmark_has_no_label(annotations):
    annotations.toggle_bookmark(43, 3, 16)
    assert annotations.bookmark_label(43, 3, 16) == ""


def test_labelling_names_the_bookmark(annotations):
    annotations.toggle_bookmark(43, 3, 16)
    annotations.label_bookmark(43, 3, 16, "the famous one")
    assert annotations.bookmark_label(43, 3, 16) == "the famous one"


def test_labelling_an_unmarked_verse_bookmarks_it(annotations):
    # Naming a verse is a clear enough statement that you want to keep it.
    annotations.label_bookmark(43, 3, 17, "context for 16")
    assert annotations.is_bookmarked(43, 3, 17)
    assert annotations.bookmark_label(43, 3, 17) == "context for 16"


def test_a_label_can_be_cleared_without_losing_the_bookmark(annotations):
    annotations.label_bookmark(43, 3, 16, "temporary")
    annotations.label_bookmark(43, 3, 16, "")
    assert annotations.bookmark_label(43, 3, 16) == ""
    assert annotations.is_bookmarked(43, 3, 16)


def test_relabelling_replaces_rather_than_duplicates(annotations):
    annotations.label_bookmark(43, 3, 16, "first")
    annotations.label_bookmark(43, 3, 16, "second")
    assert annotations.bookmark_label(43, 3, 16) == "second"
    assert len(annotations.list_bookmarks()) == 1


def test_the_label_of_a_verse_that_was_never_bookmarked_is_empty(annotations):
    assert annotations.bookmark_label(1, 1, 1) == ""


def test_canonical_order_reads_genesis_to_revelation(annotations):
    annotations.toggle_bookmark(66, 22, 21)
    annotations.toggle_bookmark(1, 1, 1)
    annotations.toggle_bookmark(43, 3, 16)
    names = [row["book_name"] for row in annotations.list_bookmarks(ORDER_CANONICAL)]
    assert names == ["Genesis", "John", "Revelation"]


def test_the_default_order_puts_the_newest_first(annotations):
    annotations.toggle_bookmark(1, 1, 1)
    annotations.toggle_bookmark(43, 3, 16)
    assert annotations.list_bookmarks()[0]["book_name"] == "John"


def test_an_empty_filter_returns_everything(annotations):
    annotations.toggle_bookmark(1, 1, 1)
    annotations.toggle_bookmark(43, 3, 16)
    assert len(annotations.find_bookmarks("   ")) == 2


def test_filtering_matches_a_label(annotations):
    annotations.label_bookmark(43, 3, 16, "Answered prayer")
    annotations.toggle_bookmark(1, 1, 1)
    found = annotations.find_bookmarks("answered")
    assert [r["book_name"] for r in found] == ["John"]


def test_filtering_matches_a_reference(annotations):
    annotations.toggle_bookmark(43, 3, 16)
    annotations.toggle_bookmark(1, 1, 1)
    assert [r["book_name"] for r in annotations.find_bookmarks("john 3")] == ["John"]


def test_filtering_survives_an_unlabelled_bookmark(annotations):
    # A NULL label used to be the obvious way to make a filter throw.
    annotations.toggle_bookmark(1, 1, 1)
    assert annotations.find_bookmarks("nothing matches this") == []


def test_filtering_keeps_the_requested_order(annotations):
    annotations.label_bookmark(66, 22, 21, "keep")
    annotations.label_bookmark(1, 1, 1, "keep")
    names = [r["book_name"] for r in annotations.find_bookmarks("keep", ORDER_CANONICAL)]
    assert names == ["Genesis", "Revelation"]


def test_deleting_a_note_removes_it(annotations):
    note_id = annotations.add_note(1, 1, 1, "temporary")
    annotations.delete_note(note_id)
    assert annotations.get_notes(1, 1, 1) == []


# --- Bookmark folders ---


def test_a_new_bookmark_has_no_folder(annotations):
    annotations.toggle_bookmark(1, 1, 1)
    row = annotations.list_bookmarks()[0]
    assert row["folder_id"] is None
    assert row["folder_name"] is None


def test_filing_a_bookmark_into_a_folder(annotations):
    folder_id = annotations.create_folder("Favourites")
    annotations.set_bookmark_folder(1, 1, 1, folder_id)
    row = annotations.list_bookmarks()[0]
    assert row["folder_name"] == "Favourites"


def test_creating_the_same_folder_name_twice_reuses_it(annotations):
    first = annotations.create_folder("Study")
    second = annotations.create_folder("Study")
    assert first == second
    assert len(annotations.list_folders()) == 1


def test_deleting_a_folder_unfiles_its_bookmarks_rather_than_deleting_them(annotations):
    folder_id = annotations.create_folder("Study")
    annotations.set_bookmark_folder(1, 1, 1, folder_id)
    annotations.delete_folder(folder_id)
    row = annotations.list_bookmarks()[0]
    assert row["folder_id"] is None
    assert annotations.is_bookmarked(1, 1, 1) is True


def test_renaming_a_folder(annotations):
    folder_id = annotations.create_folder("Old name")
    annotations.rename_folder(folder_id, "New name")
    assert annotations.list_folders()[0]["name"] == "New name"


# --- Tags ---


def test_tagging_a_verse(annotations):
    annotations.tag_verse(1, 1, 1, "Creation")
    assert annotations.tags_for_verse(1, 1, 1) == ["creation"]


def test_tag_names_are_case_insensitive(annotations):
    annotations.tag_verse(1, 1, 1, "Creation")
    annotations.tag_verse(1, 1, 2, "creation")
    assert len(annotations.list_tags()) == 1


def test_untagging_a_verse(annotations):
    annotations.tag_verse(1, 1, 1, "Creation")
    annotations.untag_verse(1, 1, 1, "Creation")
    assert annotations.tags_for_verse(1, 1, 1) == []


def test_finding_every_verse_with_a_tag(annotations):
    annotations.tag_verse(1, 1, 1, "Creation")
    annotations.tag_verse(1, 1, 2, "Creation")
    rows = annotations.verses_tagged("Creation")
    assert [(r["chapter"], r["verse"]) for r in rows] == [(1, 1), (1, 2)]


def test_tagging_a_note(annotations):
    note_id = annotations.add_note(1, 1, 1, "a note")
    annotations.tag_note(note_id, "Reflection")
    assert annotations.tags_for_note(note_id) == ["reflection"]


# --- Favourites ---


def test_toggling_a_favourite(annotations):
    assert annotations.is_favourite(1, 1, 1) is False
    assert annotations.toggle_favourite(1, 1, 1) is True
    assert annotations.is_favourite(1, 1, 1) is True
    assert annotations.toggle_favourite(1, 1, 1) is False
    assert annotations.is_favourite(1, 1, 1) is False


def test_favourites_are_distinct_from_bookmarks(annotations):
    annotations.toggle_favourite(1, 1, 1)
    assert annotations.is_bookmarked(1, 1, 1) is False


def test_listing_favourites_newest_first(annotations):
    annotations.toggle_favourite(1, 1, 1)
    annotations.toggle_favourite(43, 3, 16)
    rows = annotations.list_favourites()
    assert [r["book_name"] for r in rows] == ["John", "Genesis"]
