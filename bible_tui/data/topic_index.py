"""A curated theme/topic index - hand-authored static data, same precedent
as ``prayer_prompts.py`` and ``book_aliases.py``: not imported from
anywhere, just a small, useful list. Each topic pairs a name with a query
string that ``SearchService.search()`` already knows how to run, so
picking a topic just replays a canned search rather than needing any new
results-rendering code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    name: str
    query: str


TOPICS: tuple[Topic, ...] = (
    Topic("Faith", "faith"),
    Topic("Love", "love"),
    Topic("Hope", "hope"),
    Topic("Grace", "grace"),
    Topic("Forgiveness", "forgive"),
    Topic("Prayer", "pray"),
    Topic("Salvation", "salvation"),
    Topic("Fear & anxiety", "fear not"),
    Topic("Wisdom", "wisdom"),
    Topic("Peace", "peace"),
    Topic("Joy", "joy"),
    Topic("Patience", "patience"),
    Topic("Humility", "humble"),
    Topic("Obedience", "obey"),
    Topic("Repentance", "repent"),
    Topic("The Holy Spirit", "holy spirit"),
    Topic("Marriage & family", "marriage"),
    Topic("Justice", "justice"),
    Topic("Suffering", "suffering"),
    Topic("Eternal life", "eternal life"),
)
