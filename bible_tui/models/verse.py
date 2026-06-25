from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Verse:
    id: int
    book_id: int
    book_name: str
    chapter: int
    verse: int
    text: str

    @property
    def reference(self) -> str:
        return f"{self.book_name} {self.chapter}:{self.verse}"

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Verse":
        return cls(
            id=row["id"],
            book_id=row["book_id"],
            book_name=row["book_name"],
            chapter=row["chapter"],
            verse=row["verse"],
            text=row["text"],
        )


@dataclass(frozen=True)
class Chapter:
    book_id: int
    book_name: str
    chapter: int
    verses: list[Verse]
