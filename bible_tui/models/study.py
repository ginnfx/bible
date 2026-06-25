from dataclasses import dataclass


@dataclass(frozen=True)
class StrongsEntry:
    code: str
    language: str  # 'Hebrew' or 'Greek'
    transliteration: str
    definition: str
    pronunciation: str


@dataclass(frozen=True)
class InterlinearWord:
    word: str  # the English word as it appears in the verse
    strongs_code: str
    transliteration: str
    definition: str
    language: str  # 'Hebrew' or 'Greek'


@dataclass(frozen=True)
class CrossReference:
    book_id: int
    book_name: str
    chapter: int
    verse: int
    votes: int


@dataclass(frozen=True)
class CommentaryEntry:
    author: str
    text: str
    source_url: str | None
