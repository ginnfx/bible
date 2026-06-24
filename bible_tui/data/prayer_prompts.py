"""Static prompts behind Prayer mode - the classic ACTS framework
(Adoration, Confession, Thanksgiving, Supplication), one line each. Same
kind of static reference data as ``book_aliases.py``: small, hand-typed,
and worth testing for shape rather than for the words themselves.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrayerPrompt:
    section: str
    prompt: str


ACTS_PROMPTS: tuple[PrayerPrompt, ...] = (
    PrayerPrompt("Adoration", "Who is God, right now? Name what you love about Him."),
    PrayerPrompt("Confession", "What's weighing on your conscience?"),
    PrayerPrompt("Thanksgiving", "What from today deserves a 'thank you'?"),
    PrayerPrompt("Supplication", "What do you need - for yourself, or someone else?"),
)
