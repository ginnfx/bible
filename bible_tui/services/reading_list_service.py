"""Personal reading lists: ad-hoc collections of verses, distinct from a
bookmark (a single marked place) or a reading plan (a day-scheduled pace
through whole chapters). A list is just a name and a bag of verse
addresses a reader chose to group together."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..data.repository import BibleRepository


@dataclass
class ReadingListService:
    repo: BibleRepository

    def create_list(self, name: str) -> int:
        return self.repo.create_reading_list(name)

    def list_lists(self) -> list[sqlite3.Row]:
        return self.repo.list_reading_lists()

    def rename_list(self, list_id: int, name: str) -> None:
        self.repo.rename_reading_list(list_id, name)

    def delete_list(self, list_id: int) -> None:
        self.repo.delete_reading_list(list_id)

    def add_verse(self, list_id: int, book_id: int, chapter: int, verse: int) -> int:
        return self.repo.add_to_reading_list(list_id, book_id, chapter, verse)

    def remove_item(self, item_id: int) -> None:
        self.repo.remove_from_reading_list(item_id)

    def items(self, list_id: int) -> list[sqlite3.Row]:
        return self.repo.reading_list_items(list_id)
