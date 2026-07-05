from __future__ import annotations

from dataclasses import dataclass

from ..data.repository import BibleRepository
from ..models.study import CommentaryEntry, CrossReference, InterlinearWord, StrongsEntry


@dataclass
class StudyService:
    repo: BibleRepository

    def interlinear_for_verse(self, book_id: int, chapter: int, verse: int) -> list[InterlinearWord]:
        rows = self.repo.get_strongs_for_verse(book_id, chapter, verse)
        return [
            InterlinearWord(
                word=r["word"],
                strongs_code=r["code"],
                transliteration=r["transliteration"] or "",
                definition=r["definition"],
                language=r["language"],
            )
            for r in rows
        ]

    def cross_references(
        self, book_id: int, chapter: int, verse: int, translation_code: str, limit: int = 15
    ) -> list[CrossReference]:
        rows = self.repo.get_cross_references(book_id, chapter, verse, translation_code, limit)
        return [
            CrossReference(
                book_id=r["book_id"], book_name=r["book_name"], chapter=r["chapter"], verse=r["verse"],
                votes=r["votes"],
            )
            for r in rows
        ]

    def commentary(self, book_id: int, chapter: int, verse: int) -> list[CommentaryEntry]:
        rows = self.repo.get_commentary(book_id, chapter, verse)
        return [CommentaryEntry(author=r["author"], text=r["text"], source_url=r["source_url"]) for r in rows]

    def study_markers_for_chapter(self, book_id: int, chapter: int) -> set[int]:
        return self.repo.study_markers_for_chapter(book_id, chapter)

    def search_strongs(self, query: str) -> list[StrongsEntry]:
        """Bible dictionary lookup - Hebrew/Greek words only, not a plain-
        English dictionary of names and customs."""
        if not query.strip():
            return []
        rows = self.repo.search_strongs(query)
        return [
            StrongsEntry(
                code=r["code"],
                language=r["language"],
                transliteration=r["transliteration"],
                definition=r["definition"],
                pronunciation=r["pronunciation"],
            )
            for r in rows
        ]
