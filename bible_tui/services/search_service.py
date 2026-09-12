"""Full-text search: query building, filtering, typo tolerance, history.

Search runs in three escalating passes so a query that finds nothing still
has a chance of finding what was meant:

1. the query exactly as written;
2. every bare word retried as a prefix, which rescues half-typed words;
3. each unmatched word replaced with the closest term in the index, which
   rescues actual misspellings.

Whichever pass produced results is reported back, so the UI can say *why*
it's showing what it's showing rather than silently changing the query.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from ..data.query import ParsedQuery, parse, with_prefix_matching
from ..data.repository import BibleRepository
from ..models.verse import Verse

#: How search resolved, in the order the passes are tried.
EXACT = "exact"
PREFIX = "prefix"
CORRECTED = "corrected"

#: Ratio above which a vocabulary term counts as a plausible correction.
#: Below ~0.75 the suggestions stop resembling the typo.
_SIMILARITY_CUTOFF = 0.75

#: How many of difflib's matches to re-rank. difflib scores purely on
#: character overlap, which prefers a short obscure word ("sherd") over the
#: longer common one the typist meant ("shepherd"), so its ordering is
#: treated as a shortlist rather than an answer.
_SHORTLIST = 8

#: Words too short to correct usefully - every three-letter typo is close to
#: a dozen real words.
_MIN_CORRECTABLE_LENGTH = 4

#: A term has to appear at least this often before it is offered as a
#: spelling correction - in a corpus this size, a one-off token is far more
#: likely to be a proper noun than the word someone meant. Small fixtures
#: override it, since there every term is a one-off.
DEFAULT_VOCABULARY_FLOOR = 2

#: Queries remembered for the history list.
HISTORY_LIMIT = 25

_HISTORY_KEY = "search_history"
#: Named saves, distinct from the unnamed recent-searches history above -
#: a full SearchFilters, not just a query string, so a saved search
#: reproduces its scope too, not just what was typed.
_SAVED_KEY = "saved_searches"


@dataclass(frozen=True)
class SearchFilters:
    """Scope restrictions. All optional; unset means "search everything"."""

    testament: str | None = None  # 'OT' or 'NT'
    category: str | None = None  # 'Gospels', 'Law', …
    book_id: int | None = None

    @property
    def is_active(self) -> bool:
        return any((self.testament, self.category, self.book_id))

    def describe(self, book_name: str | None = None) -> str:
        """A short label for the search screen's scope indicator."""
        if self.book_id and book_name:
            return book_name
        if self.category:
            return self.category
        if self.testament:
            return "Old Testament" if self.testament == "OT" else "New Testament"
        return "Whole Bible"


@dataclass(frozen=True)
class SearchOutcome:
    """Results plus enough context for the UI to explain them."""

    results: list[Verse]
    terms: tuple[str, ...]
    resolution: str = EXACT
    #: Populated when `resolution` is CORRECTED: {typed: used}.
    corrections: dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.results)


@dataclass
class SearchService:
    repo: BibleRepository
    vocabulary_floor: int = DEFAULT_VOCABULARY_FLOOR

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        translation_code: str,
        filters: SearchFilters | None = None,
        limit: int = 100,
        fuzzy: bool = True,
    ) -> SearchOutcome:
        parsed = parse(query)
        if not parsed:
            return SearchOutcome([], ())

        filters = filters or SearchFilters()

        results = self._run(parsed, translation_code, filters, limit)
        if results or not fuzzy:
            return SearchOutcome(results, parsed.terms, EXACT)

        prefixed = with_prefix_matching(parsed)
        results = self._run(prefixed, translation_code, filters, limit)
        if results:
            return SearchOutcome(results, parsed.terms, PREFIX)

        corrected, corrections = self._correct(parsed)
        if corrections:
            results = self._run(corrected, translation_code, filters, limit)
            if results:
                return SearchOutcome(results, corrected.terms, CORRECTED, corrections)

        return SearchOutcome([], parsed.terms)

    def search_within(
        self,
        query: str,
        previous: list[Verse],
        translation_code: str,
        limit: int = 100,
    ) -> SearchOutcome:
        """Narrow an existing result set instead of the whole Bible.

        Runs the new query unrestricted and intersects on verse id, which
        keeps FTS5 doing the matching while the refinement stays exact.
        """
        if not previous:
            return SearchOutcome([], ())
        keep = {v.id for v in previous}
        outcome = self.search(query, translation_code, limit=max(limit, len(keep)))
        narrowed = [v for v in outcome.results if v.id in keep]
        return SearchOutcome(narrowed[:limit], outcome.terms, outcome.resolution, outcome.corrections)

    def _run(
        self,
        parsed: ParsedQuery,
        translation_code: str,
        filters: SearchFilters,
        limit: int,
    ) -> list[Verse]:
        return self.repo.search(
            parsed.expression,
            translation_code,
            testament=filters.testament,
            category=filters.category,
            book_id=filters.book_id,
            limit=limit,
        )

    def _correct(self, parsed: ParsedQuery) -> tuple[ParsedQuery, dict[str, str]]:
        """Swap misspelled words for the closest term in the search index."""
        vocabulary = self.repo.vocabulary(self.vocabulary_floor)
        if not vocabulary:
            return parsed, {}

        corrections: dict[str, str] = {}
        expression = parsed.expression
        for word in dict.fromkeys(parsed.terms):
            if len(word) < _MIN_CORRECTABLE_LENGTH or word.lower() in vocabulary:
                continue
            match = self._best_correction(word, vocabulary)
            if match:
                corrections[word] = match
                # word.replace() only catches a word quoted on its own; a
                # word inside a multi-word phrase like "believeing this"
                # needs a word-boundary swap instead.
                expression = re.sub(rf"\b{re.escape(word)}\b", match, expression)

        if not corrections:
            return parsed, {}
        terms = tuple(corrections.get(t, t) for t in parsed.terms)
        return ParsedQuery(expression, terms), corrections

    def suggestions(self, word: str, limit: int = 3) -> list[str]:
        """Alternative spellings for a word, for a "did you mean" prompt."""
        vocabulary = self.repo.vocabulary(self.vocabulary_floor)
        if not vocabulary or len(word) < _MIN_CORRECTABLE_LENGTH:
            return []
        return self._ranked_candidates(word, vocabulary)[:limit]

    @staticmethod
    def _ranked_candidates(word: str, vocabulary: dict[str, int]) -> list[str]:
        """difflib's shortlist, re-ordered by how a typist actually errs.

        Typos overwhelmingly preserve the start of the word, and the intended
        word is far more likely to be a common one - so shared prefix length
        leads, corpus frequency breaks ties, and raw character similarity is
        only the last word.
        """
        lowered = word.lower()
        shortlist = difflib.get_close_matches(
            lowered, vocabulary.keys(), n=_SHORTLIST, cutoff=_SIMILARITY_CUTOFF
        )
        return sorted(
            shortlist,
            key=lambda term: (
                -_shared_prefix(lowered, term),
                -vocabulary.get(term, 0),
                -difflib.SequenceMatcher(None, lowered, term).ratio(),
            ),
        )

    def _best_correction(self, word: str, vocabulary: dict[str, int]) -> str | None:
        candidates = self._ranked_candidates(word, vocabulary)
        return candidates[0] if candidates else None

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def history(self) -> list[str]:
        stored = self.repo.get_setting(_HISTORY_KEY, [])
        return [q for q in stored if isinstance(q, str)] if isinstance(stored, list) else []

    def remember(self, query: str) -> None:
        """Record a query, most recent first, without duplicates."""
        query = query.strip()
        if not query:
            return
        entries = [q for q in self.history() if q != query]
        entries.insert(0, query)
        self.repo.set_setting(_HISTORY_KEY, entries[:HISTORY_LIMIT])

    def forget_history(self) -> None:
        self.repo.set_setting(_HISTORY_KEY, [])

    # ------------------------------------------------------------------
    # Named saves
    # ------------------------------------------------------------------

    def saved_searches(self) -> list[dict]:
        stored = self.repo.get_setting(_SAVED_KEY, [])
        return [e for e in stored if isinstance(e, dict) and e.get("name")] if isinstance(stored, list) else []

    def save_search(self, name: str, query: str, filters: SearchFilters) -> None:
        """Record a named search - full filters, not just the query text.
        Saving under an existing name replaces it rather than duplicating."""
        name = name.strip()
        query = query.strip()
        if not name or not query:
            return
        entries = [e for e in self.saved_searches() if e["name"] != name]
        entries.insert(
            0,
            {
                "name": name,
                "query": query,
                "testament": filters.testament,
                "category": filters.category,
                "book_id": filters.book_id,
            },
        )
        self.repo.set_setting(_SAVED_KEY, entries)

    def delete_saved_search(self, name: str) -> None:
        entries = [e for e in self.saved_searches() if e["name"] != name]
        self.repo.set_setting(_SAVED_KEY, entries)


def _shared_prefix(a: str, b: str) -> int:
    length = 0
    for x, y in zip(a, b):
        if x != y:
            break
        length += 1
    return length
