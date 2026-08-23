import pytest

from bible_tui.data.reference_parser import parse_bible_url, parse_reference


@pytest.mark.parametrize(
    "raw, book_query, chapter, verse_start, verse_end",
    [
        ("Genesis 1:1", "Genesis", 1, 1, None),
        ("gen 1", "gen", 1, None, None),
        ("1 cor 13:4-7", "1 cor", 13, 4, 7),
        ("jn3:16", "jn", 3, 16, None),
        ("Genesis", "Genesis", None, None, None),
        ("  Psalms   23 : 1  ", "Psalms", 23, 1, None),
    ],
)
def test_parse_reference_shapes(raw, book_query, chapter, verse_start, verse_end):
    parsed = parse_reference(raw)
    assert parsed is not None
    assert parsed.book_query == book_query
    assert parsed.chapter == chapter
    assert parsed.verse_start == verse_start
    assert parsed.verse_end == verse_end


@pytest.mark.parametrize("raw", ["", "   ", "1:1", "42"])
def test_parse_reference_rejects_bookless_input(raw):
    # A bare chapter/verse number with no leading book name isn't a valid
    # reference on its own - the book group requires at least one letter.
    assert parse_reference(raw) is None


# ----------------------------------------------------------------------
# bible:// URLs
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("bible://John/3/16", "John 3:16"),
        ("bible:John/3/16", "John 3:16"),  # no "//" authority marker
        ("bible://Genesis/1", "Genesis 1"),
        ("bible://Genesis", "Genesis"),
        ("bible://1-corinthians/13/4-7", "1 corinthians 13:4-7"),
        ("bible://John%20the%20Baptist/1", "John the Baptist 1"),
        ("BIBLE://John/3/16", "John 3:16"),  # scheme match is case-insensitive
    ],
)
def test_parse_bible_url_shapes(url, expected):
    assert parse_bible_url(url) == expected


@pytest.mark.parametrize("url", ["https://example.com/John/3/16", "not-a-url", ""])
def test_parse_bible_url_rejects_other_schemes(url):
    assert parse_bible_url(url) is None


def test_a_parsed_bible_url_is_itself_a_valid_reference():
    text = parse_bible_url("bible://1-corinthians/13/4-7")
    parsed = parse_reference(text)
    assert parsed is not None
    assert parsed.book_query == "1 corinthians"
    assert (parsed.chapter, parsed.verse_start, parsed.verse_end) == (13, 4, 7)
