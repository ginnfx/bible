"""Reading-mode mechanics: memorisation, speed-reading, dictation, quiz,
sermon pagination and the contemplative-mode timer.

Each mode is a pure transform of verse text rather than a widget's own
logic - the algorithm behind "hide a growing share of words" or "score what
was typed against the verse" is checked without a running app, and the same
functions could drive a different screen (or a web view) unchanged.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from ..models.verse import Verse

#: Words this short (the, and, he, his...) are never blanked out - hiding a
#: connector teaches nothing, it just makes the puzzle needlessly annoying.
_MIN_HIDEABLE_LENGTH = 4

_WORD_RE = re.compile(r"[A-Za-z']+")

# ---------------------------------------------------------------------------
# Memorisation - progressive word hiding
# ---------------------------------------------------------------------------

#: Five stages: stage 0 is a plain read-through, stage 5 hides every
#: hideable word so reciting it is the only way through.
MEMORISATION_STAGES = 5


def hide_words(text: str, stage: int, seed: int) -> str:
    """Replace a growing share of *text*'s words with underscores.

    *seed* pins one random ordering of the hideable words; *stage* only
    changes how far into that ordering the cut falls. That means moving from
    stage 2 to stage 3 with the same seed only ever adds blanks - a word
    hidden at a lower stage is never un-hidden at a higher one, so repeated
    presses of "hide more" are a one-way ratchet rather than a reshuffle.
    """
    stage = max(0, min(stage, MEMORISATION_STAGES))
    if stage == 0:
        return text

    matches = list(_WORD_RE.finditer(text))
    hideable = [i for i, m in enumerate(matches) if len(m.group(0)) >= _MIN_HIDEABLE_LENGTH]
    if not hideable:
        return text

    order = hideable.copy()
    random.Random(seed).shuffle(order)
    cutoff = max(1, round(len(order) * stage / MEMORISATION_STAGES))
    hidden = set(order[:cutoff])

    return _replace_matches(text, matches, hidden)


def _replace_matches(text: str, matches: list[re.Match], hidden: set[int]) -> str:
    out: list[str] = []
    cursor = 0
    for i, match in enumerate(matches):
        out.append(text[cursor : match.start()])
        word = match.group(0)
        out.append("_" * len(word) if i in hidden else word)
        cursor = match.end()
    out.append(text[cursor:])
    return "".join(out)


# ---------------------------------------------------------------------------
# Speed-reading - RSVP word stream
# ---------------------------------------------------------------------------


def rsvp_words(text: str) -> list[str]:
    """Split into a display sequence for word-by-word (RSVP) reading.

    Splits on whitespace rather than :data:`_WORD_RE` - punctuation glued to
    a word (a comma, a colon) is part of what flashes past before the next
    word replaces it, not something to strip out.
    """
    return text.split()


def wpm_to_seconds_per_word(wpm: int) -> float:
    """Convert a words-per-minute pace into the delay between words."""
    if wpm <= 0:
        raise ValueError("wpm must be positive")
    return 60.0 / wpm


# ---------------------------------------------------------------------------
# Dictation - type it, check it
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DictationResult:
    expected_words: list[str]
    typed_words: list[str]
    #: One entry per expected word - True where the typed word at that
    #: position matched, case-insensitively. Never lengthened by extra
    #: typed words beyond the verse.
    correct: list[bool]
    accuracy: float


def score_dictation(expected: str, typed: str) -> DictationResult:
    """Compare what was typed against *expected*, word by word and by
    position - a slip on word 3 doesn't cascade into marking every word
    after it wrong, the way a naive full-string diff would."""
    expected_words = _WORD_RE.findall(expected)
    typed_words = _WORD_RE.findall(typed)

    correct = [
        i < len(typed_words) and typed_words[i].lower() == word.lower()
        for i, word in enumerate(expected_words)
    ]
    accuracy = sum(correct) / len(expected_words) if expected_words else 0.0
    return DictationResult(
        expected_words=expected_words, typed_words=typed_words, correct=correct, accuracy=accuracy
    )


# ---------------------------------------------------------------------------
# Quiz - fill in the blank
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuizQuestion:
    #: The verse text with exactly one word replaced by underscores of the
    #: same length.
    prompt: str
    answer: str


def generate_quiz(text: str, seed: int) -> QuizQuestion | None:
    """Blank one random hideable word out of *text*. ``None`` when the verse
    has nothing long enough to blank (e.g. "He is Lord.") rather than
    forcing a question out of it."""
    matches = list(_WORD_RE.finditer(text))
    hideable = [m for m in matches if len(m.group(0)) >= _MIN_HIDEABLE_LENGTH]
    if not hideable:
        return None

    target = random.Random(seed).choice(hideable)
    answer = target.group(0)
    prompt = text[: target.start()] + "_" * len(answer) + text[target.end() :]
    return QuizQuestion(prompt=prompt, answer=answer)


# ---------------------------------------------------------------------------
# Sermon - one verse per slide
# ---------------------------------------------------------------------------


def sermon_slides(verses: list[Verse]) -> list[tuple[str, str]]:
    """(verse-number label, text) pairs, one per slide, in chapter order -
    a large-text presentation is really just "one verse, paced by hand"."""
    return [(str(v.verse), v.text) for v in verses]


# ---------------------------------------------------------------------------
# Contemplative - a timer that never sounds rushed
# ---------------------------------------------------------------------------


def format_timer(remaining_seconds: int) -> str:
    """"1:15 remaining" while counting down, "Take your time." right at
    zero, "+0:22" once elapsed - the reader is never told they're behind;
    a reflection timer that nags isn't a reflection timer."""
    if remaining_seconds > 0:
        minutes, seconds = divmod(remaining_seconds, 60)
        return f"{minutes}:{seconds:02d} remaining"
    if remaining_seconds == 0:
        return "Take your time."
    minutes, seconds = divmod(-remaining_seconds, 60)
    return f"+{minutes}:{seconds:02d}"
