"""Reading-mode mechanics: memorisation, speed-reading, dictation and quiz.

Pure text transforms - no widget, no database - so the algorithm behind
"hide a growing share of words" or "score what was typed against the verse"
is checked without a running app.
"""

from __future__ import annotations

import pytest

from bible_tui.models.verse import Verse
from bible_tui.services.reading_mode_service import (
    MEMORISATION_STAGES,
    format_timer,
    generate_quiz,
    hide_words,
    rsvp_words,
    score_dictation,
    sermon_slides,
    wpm_to_seconds_per_word,
)

VERSE = "For God so loved the world, that he gave his only begotten Son."


# ----------------------------------------------------------------------
# Memorisation - progressive word hiding
# ----------------------------------------------------------------------


def test_stage_zero_hides_nothing():
    assert hide_words(VERSE, 0, seed=1) == VERSE


def test_the_final_stage_hides_every_hideable_word():
    hidden = hide_words(VERSE, MEMORISATION_STAGES, seed=1)
    assert "loved" not in hidden
    assert "world" not in hidden
    assert "begotten" not in hidden


def test_short_connector_words_are_never_hidden():
    # Blanking "the" or "he" would teach nothing.
    hidden = hide_words(VERSE, MEMORISATION_STAGES, seed=1)
    assert " the " in hidden
    assert " he " in hidden


def test_hiding_only_grows_as_the_stage_rises():
    # Every word blank at stage 2 must still be blank at stage 3 - moving up
    # a stage should only add blanks, never un-hide a word you'd already got.
    stage2 = hide_words(VERSE, 2, seed=7)
    stage3 = hide_words(VERSE, 3, seed=7)
    blanks_at_2 = {i for i, ch in enumerate(stage2) if ch == "_"}
    blanks_at_3 = {i for i, ch in enumerate(stage3) if ch == "_"}
    assert blanks_at_2 <= blanks_at_3


def test_a_hidden_word_becomes_underscores_of_the_same_length():
    assert hide_words("beginning", MEMORISATION_STAGES, seed=1) == "_" * len("beginning")


def test_the_same_seed_hides_the_same_words_every_time():
    assert hide_words(VERSE, 3, seed=5) == hide_words(VERSE, 3, seed=5)


def test_different_seeds_can_hide_different_words():
    variants = {hide_words(VERSE, 2, seed=s) for s in range(10)}
    assert len(variants) > 1


def test_punctuation_and_spacing_survive_untouched():
    hidden = hide_words(VERSE, 3, seed=1)
    assert hidden.count(",") == VERSE.count(",")
    assert hidden.count(".") == VERSE.count(".")
    assert hidden.count(" ") == VERSE.count(" ")


def test_a_stage_above_the_maximum_is_clamped():
    assert hide_words(VERSE, 99, seed=1) == hide_words(VERSE, MEMORISATION_STAGES, seed=1)


def test_a_negative_stage_is_clamped_to_zero():
    assert hide_words(VERSE, -3, seed=1) == VERSE


def test_a_verse_with_no_hideable_words_is_returned_unchanged():
    assert hide_words("He is a God.", MEMORISATION_STAGES, seed=1) == "He is a God."


# ----------------------------------------------------------------------
# Speed-reading - RSVP word stream
# ----------------------------------------------------------------------


def test_rsvp_splits_on_whitespace_keeping_punctuation_attached():
    words = rsvp_words("For God so loved the world,")
    assert words[-1] == "world,"
    assert len(words) == 6


def test_rsvp_of_empty_text_is_an_empty_stream():
    assert rsvp_words("") == []


def test_wpm_converts_to_a_per_word_delay():
    assert wpm_to_seconds_per_word(60) == 1.0
    assert wpm_to_seconds_per_word(120) == 0.5


@pytest.mark.parametrize("wpm", [0, -10])
def test_wpm_must_be_positive(wpm):
    with pytest.raises(ValueError):
        wpm_to_seconds_per_word(wpm)


# ----------------------------------------------------------------------
# Dictation - type it, check it
# ----------------------------------------------------------------------


def test_a_perfect_match_scores_full_accuracy():
    result = score_dictation(VERSE, VERSE)
    assert result.accuracy == 1.0
    assert all(result.correct)


def test_dictation_is_case_insensitive():
    result = score_dictation("God is love", "god IS Love")
    assert result.accuracy == 1.0


def test_a_missing_tail_scores_only_the_words_actually_typed():
    result = score_dictation("For God so loved the world", "For God so")
    assert result.correct == [True, True, True, False, False, False]
    assert result.accuracy == 0.5


def test_a_wrong_word_is_marked_incorrect_but_does_not_shift_the_rest():
    result = score_dictation("For God so loved", "For Gods so loved")
    assert result.correct == [True, False, True, True]


def test_extra_typed_words_beyond_the_verse_are_ignored():
    result = score_dictation("God is love", "God is love and more")
    assert result.accuracy == 1.0


def test_an_empty_expected_verse_scores_zero_rather_than_dividing_by_zero():
    result = score_dictation("", "anything")
    assert result.accuracy == 0.0
    assert result.correct == []


# ----------------------------------------------------------------------
# Quiz - fill in the blank
# ----------------------------------------------------------------------


def test_a_quiz_question_blanks_exactly_one_word():
    question = generate_quiz(VERSE, seed=1)
    assert question is not None
    assert question.answer not in question.prompt


def test_the_blank_is_the_same_length_as_the_answer():
    question = generate_quiz(VERSE, seed=1)
    assert "_" * len(question.answer) in question.prompt


def test_everything_but_the_answer_survives_in_the_prompt():
    question = generate_quiz(VERSE, seed=1)
    assert question.prompt.replace("_" * len(question.answer), question.answer) == VERSE


def test_a_verse_with_no_hideable_words_yields_no_question():
    assert generate_quiz("He is a God.", seed=1) is None


def test_the_same_seed_asks_the_same_question():
    assert generate_quiz(VERSE, seed=3) == generate_quiz(VERSE, seed=3)


def test_different_seeds_can_ask_different_questions():
    answers = {generate_quiz(VERSE, seed=s).answer for s in range(10)}
    assert len(answers) > 1


# ----------------------------------------------------------------------
# Sermon - one verse per slide
# ----------------------------------------------------------------------

_VERSES = [
    Verse(id=1, book_id=1, book_name="Genesis", chapter=1, verse=1, text="In the beginning."),
    Verse(id=2, book_id=1, book_name="Genesis", chapter=1, verse=2, text="And the earth was void."),
    Verse(id=3, book_id=1, book_name="Genesis", chapter=1, verse=3, text="Let there be light."),
]


def test_a_slide_per_verse_in_chapter_order():
    slides = sermon_slides(_VERSES)
    assert slides == [
        ("1", "In the beginning."),
        ("2", "And the earth was void."),
        ("3", "Let there be light."),
    ]


def test_an_empty_chapter_yields_no_slides():
    assert sermon_slides([]) == []


# ----------------------------------------------------------------------
# Contemplative - a timer that never sounds rushed
# ----------------------------------------------------------------------


def test_a_positive_remaining_time_counts_down():
    assert format_timer(90) == "1:30 remaining"
    assert format_timer(5) == "0:05 remaining"


def test_zero_remaining_reads_as_take_your_time():
    assert format_timer(0) == "Take your time."


def test_elapsed_time_counts_up_instead_of_flashing_a_warning():
    assert format_timer(-15) == "+0:15"
    assert format_timer(-75) == "+1:15"
