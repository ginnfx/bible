from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class ParsedReference:
    book_query: str
    chapter: int | None
    verse_start: int | None
    verse_end: int | None


_PATTERN = re.compile(
    r"^\s*(?P<book>[1-3]?\s?[A-Za-z]+)\s*"
    r"(?:(?P<chapter>\d+)"
    r"(?:\s*:\s*(?P<vstart>\d+)(?:\s*-\s*(?P<vend>\d+))?)?)?\s*$"
)


def parse_reference(raw: str) -> ParsedReference | None:
    """Parses 'Genesis 1:1', 'gen 1', '1 cor 13:4-7', 'jn3:16' into components.

    Returns None if the string doesn't match a plausible reference shape.
    The caller resolves book_query against the books table via
    BibleRepository.get_book_by_name_or_abbrev, since abbreviation matching
    needs the database and doesn't belong in a pure parser.
    """
    match = _PATTERN.match(raw.strip())
    if not match:
        return None
    return ParsedReference(
        book_query=match.group("book").strip(),
        chapter=int(match.group("chapter")) if match.group("chapter") else None,
        verse_start=int(match.group("vstart")) if match.group("vstart") else None,
        verse_end=int(match.group("vend")) if match.group("vend") else None,
    )


def parse_bible_url(url: str) -> str | None:
    """Converts a ``bible://`` URL into the reference text `parse_reference`
    already understands, so a URL and a typed reference share one parsing
    path from there on rather than duplicating book resolution here.

    Accepts ``bible://John/3/16``, ``bible:John/3`` (no ``//``), and a
    hyphenated book segment (``bible://1-corinthians/13/4-7``) - hyphens
    and ``%20`` both become spaces, both reusing `parse_reference`'s
    existing forgiving book-name matching once turned into plain text.
    Returns None for anything that isn't a ``bible:`` URL at all; an
    unparseable reference inside a well-formed one is left for
    `parse_reference` to reject the normal way.
    """
    parsed = urlparse(url)
    if parsed.scheme.lower() != "bible":
        return None
    # A URL author may or may not include the "//" authority marker; both
    # land the book name in a different place, so check both.
    segments = [s for s in ([parsed.netloc] + parsed.path.split("/")) if s]
    if not segments:
        return None
    book = unquote(segments[0]).replace("-", " ")
    rest = segments[1:]
    if not rest:
        return book
    reference = f"{book} {rest[0]}"
    if len(rest) > 1:
        reference += f":{rest[1]}"
    return reference
