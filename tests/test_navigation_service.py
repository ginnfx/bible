from bible_tui.services.navigation_service import NavigationService


def test_next_chapter_rolls_into_next_book(repo):
    nav = NavigationService(repo)
    # Genesis has 50 chapters in the canonical book list; chapter 50 should
    # roll into Exodus 1.
    assert nav.next_chapter(book_id=1, chapter=50) == (2, 1)


def test_next_chapter_within_same_book(repo):
    nav = NavigationService(repo)
    assert nav.next_chapter(book_id=1, chapter=1) == (1, 2)


def test_next_chapter_past_revelation_returns_none(repo):
    nav = NavigationService(repo)
    assert nav.next_chapter(book_id=66, chapter=22) is None


def test_prev_chapter_rolls_into_previous_book(repo):
    nav = NavigationService(repo)
    assert nav.prev_chapter(book_id=2, chapter=1) == (1, 50)


def test_prev_chapter_before_genesis_returns_none(repo):
    nav = NavigationService(repo)
    assert nav.prev_chapter(book_id=1, chapter=1) is None


def test_go_to_chapter_returns_verses_and_records_history(repo):
    nav = NavigationService(repo)
    verses = nav.go_to_chapter(1, 1)
    assert len(verses) == 3
    assert verses[0].reference == "Genesis 1:1"
    assert nav.current_position() == (1, 1)


def test_go_to_missing_chapter_returns_empty_and_no_history(repo):
    nav = NavigationService(repo)
    verses = nav.go_to_chapter(1, 99)
    assert verses == []
    assert nav.current_position() is None


def test_history_back_and_forward(repo):
    nav = NavigationService(repo)
    nav.go_to_chapter(1, 1)
    nav.go_to_chapter(1, 2)
    nav.go_to_chapter(43, 3)

    assert nav.back() == (1, 2)
    assert nav.back() == (1, 1)
    assert nav.back() is None  # already at the start

    assert nav.forward() == (1, 2)
    assert nav.forward() == (43, 3)
    assert nav.forward() is None  # already at the end


def test_new_jump_drops_forward_history(repo):
    nav = NavigationService(repo)
    nav.go_to_chapter(1, 1)
    nav.go_to_chapter(1, 2)
    nav.back()
    nav.go_to_chapter(43, 3)  # fresh jump while positioned mid-history

    assert nav.forward() is None
    assert nav.back() == (1, 1)
