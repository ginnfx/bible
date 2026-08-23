"""Search behaviour: query language, scope filters, typo rescue, history."""

from bible_tui.services.search_service import (
    CORRECTED,
    EXACT,
    PREFIX,
    SearchFilters,
    SearchService,
)


# ----------------------------------------------------------------------
# Basics
# ----------------------------------------------------------------------


def test_search_finds_matching_verse(repo):
    outcome = SearchService(repo).search("beginning", "KJV")
    assert len(outcome.results) == 1
    assert outcome.results[0].reference == "Genesis 1:1"
    assert outcome.resolution == EXACT


def test_search_is_case_insensitive(repo):
    assert len(SearchService(repo).search("BEGINNING", "KJV").results) == 1


def test_no_match_returns_an_empty_outcome(repo):
    outcome = SearchService(repo).search("zzzznonexistent", "KJV")
    assert outcome.results == []
    assert not outcome


def test_blank_query_returns_empty(repo):
    assert SearchService(repo).search("   ", "KJV").results == []


def test_punctuation_does_not_break_the_query(repo):
    # Apostrophes and hyphens are invalid FTS5 syntax unless quoted.
    outcome = SearchService(repo).search("don't light-years", "KJV")
    assert isinstance(outcome.results, list)


# ----------------------------------------------------------------------
# Query language
# ----------------------------------------------------------------------


def test_multiple_words_are_combined_with_and(repo):
    search = SearchService(repo)
    # "God" and "light" only co-occur in Genesis 1:3 in the fixture.
    assert {v.reference for v in search.search("God light", "KJV").results} == {"Genesis 1:3"}


def test_quoted_text_searches_as_a_phrase(repo):
    search = SearchService(repo)
    phrase = search.search('"let there be light"', "KJV").results
    loose = search.search("let there be light", "KJV").results
    assert {v.reference for v in phrase} == {"Genesis 1:3"}
    assert len(loose) >= len(phrase)


def test_or_widens_the_result_set(repo):
    search = SearchService(repo)
    combined = search.search("beginning OR firmament OR loved", "KJV").results
    assert len(combined) > len(search.search("beginning", "KJV").results)


def test_not_excludes_matches(repo):
    search = SearchService(repo)
    with_god = {v.reference for v in search.search("God", "KJV").results}
    without = {v.reference for v in search.search("God NOT beginning", "KJV").results}
    assert "Genesis 1:1" in with_god
    assert "Genesis 1:1" not in without


def test_minus_is_shorthand_for_not(repo):
    search = SearchService(repo)
    assert {v.reference for v in search.search("God -beginning", "KJV").results} == {
        v.reference for v in search.search("God NOT beginning", "KJV").results
    }


def test_wildcard_matches_by_prefix(repo):
    outcome = SearchService(repo).search("begin*", "KJV")
    assert any(v.reference == "Genesis 1:1" for v in outcome.results)


def test_near_requires_words_to_be_close_together(repo):
    search = SearchService(repo)
    # "God" and "earth" sit within a few words of each other in Genesis 1:1.
    assert search.search("God NEAR/5 earth", "KJV").results
    assert not search.search("God NEAR/1 earth", "KJV").results


# ----------------------------------------------------------------------
# Scope filters
# ----------------------------------------------------------------------


def test_book_filter_restricts_results(repo):
    outcome = SearchService(repo).search("God", "KJV", SearchFilters(book_id=43))
    assert outcome.results
    assert all(v.book_id == 43 for v in outcome.results)


def test_testament_filter_restricts_results(repo):
    outcome = SearchService(repo).search("God", "KJV", SearchFilters(testament="NT"))
    assert all(v.book_id >= 40 for v in outcome.results)


def test_category_filter_restricts_results(repo):
    outcome = SearchService(repo).search("God", "KJV", SearchFilters(category="Gospels"))
    assert all(v.book_id in {40, 41, 42, 43} for v in outcome.results)


def test_filters_describe_themselves_for_the_ui():
    assert SearchFilters().describe() == "Whole Bible"
    assert SearchFilters(testament="OT").describe() == "Old Testament"
    assert SearchFilters(testament="NT").describe() == "New Testament"
    assert SearchFilters(category="Gospels").describe() == "Gospels"
    assert SearchFilters(book_id=43).describe("John") == "John"
    assert SearchFilters().is_active is False
    assert SearchFilters(testament="OT").is_active is True


# ----------------------------------------------------------------------
# Rescue passes
# ----------------------------------------------------------------------


def test_a_half_typed_word_falls_back_to_prefix_matching(repo):
    # "begot" is not a term in the index; "begotten" is.
    outcome = SearchService(repo).search("begot", "KJV")
    assert outcome.results
    assert outcome.resolution == PREFIX


def test_a_misspelling_is_corrected_and_reported(repo):
    # Every term in this fixture occurs once, so the corpus floor that keeps
    # proper nouns out of the real suggestion list has to come down.
    outcome = SearchService(repo, vocabulary_floor=1).search("begottn", "KJV")
    assert outcome.results
    assert outcome.resolution == CORRECTED
    # The rewrite is surfaced, never silent.
    assert outcome.corrections == {"begottn": "begotten"}


def test_fuzzy_can_be_switched_off(repo):
    outcome = SearchService(repo).search("begot", "KJV", fuzzy=False)
    assert outcome.results == []


def test_corrections_prefer_the_common_word_over_a_closer_short_one(repo):
    # difflib alone scores "sherd" above "shepherd" for "shepard"; ranking by
    # shared prefix and frequency is what fixes it.
    vocabulary = {"sherd": 3, "shepherd": 500, "shed": 40}
    assert SearchService._ranked_candidates("shepard", vocabulary)[0] == "shepherd"


def test_suggestions_ignore_words_too_short_to_correct(repo):
    assert SearchService(repo, vocabulary_floor=1).suggestions("God") == []


def test_stemming_already_absorbs_some_misspellings(repo):
    # "begining" stems to the same token as "beginning", so it matches
    # outright - no rescue pass needed.
    outcome = SearchService(repo).search("begining", "KJV")
    assert outcome.resolution == EXACT
    assert outcome.results


# ----------------------------------------------------------------------
# Refine and history
# ----------------------------------------------------------------------


def test_refining_narrows_the_previous_results(repo):
    search = SearchService(repo)
    base = search.search("God", "KJV").results
    narrowed = search.search_within("light", base, "KJV").results
    assert narrowed
    assert {v.id for v in narrowed} <= {v.id for v in base}


def test_refining_an_empty_result_set_stays_empty(repo):
    assert SearchService(repo).search_within("light", [], "KJV").results == []


def test_history_records_most_recent_first_without_duplicates(repo):
    search = SearchService(repo)
    search.remember("love")
    search.remember("faith")
    search.remember("love")
    assert search.history() == ["love", "faith"]


def test_blank_queries_are_not_remembered(repo):
    search = SearchService(repo)
    search.remember("   ")
    assert search.history() == []


def test_history_can_be_cleared(repo):
    search = SearchService(repo)
    search.remember("love")
    search.forget_history()
    assert search.history() == []


# ----------------------------------------------------------------------
# Named saves
# ----------------------------------------------------------------------


def test_a_saved_search_round_trips_its_filters(repo):
    search = SearchService(repo)
    filters = SearchFilters(testament="NT", category="Gospels")
    search.save_search("Gospel of love", "love", filters)

    saved = search.saved_searches()
    assert len(saved) == 1
    assert saved[0]["name"] == "Gospel of love"
    assert saved[0]["query"] == "love"
    assert saved[0]["testament"] == "NT"
    assert saved[0]["category"] == "Gospels"


def test_saving_under_an_existing_name_replaces_it(repo):
    search = SearchService(repo)
    search.save_search("faves", "love", SearchFilters())
    search.save_search("faves", "grace", SearchFilters())
    saved = search.saved_searches()
    assert len(saved) == 1
    assert saved[0]["query"] == "grace"


def test_a_blank_name_or_query_is_not_saved(repo):
    search = SearchService(repo)
    search.save_search("", "love", SearchFilters())
    search.save_search("name only", "  ", SearchFilters())
    assert search.saved_searches() == []


def test_deleting_a_saved_search(repo):
    search = SearchService(repo)
    search.save_search("faves", "love", SearchFilters())
    search.delete_saved_search("faves")
    assert search.saved_searches() == []


def test_saved_searches_are_most_recent_first(repo):
    search = SearchService(repo)
    search.save_search("first", "love", SearchFilters())
    search.save_search("second", "grace", SearchFilters())
    assert [s["name"] for s in search.saved_searches()] == ["second", "first"]
