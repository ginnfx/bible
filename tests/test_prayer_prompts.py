"""The prayer prompts behind Prayer mode - static content, checked for
shape rather than wording (the wording is a judgment call, not a bug)."""

from __future__ import annotations

from bible_tui.data.prayer_prompts import ACTS_PROMPTS


def test_there_are_exactly_four_sections():
    assert len(ACTS_PROMPTS) == 4


def test_the_sections_are_the_classic_acts_order():
    assert [p.section for p in ACTS_PROMPTS] == [
        "Adoration",
        "Confession",
        "Thanksgiving",
        "Supplication",
    ]


def test_section_names_are_unique():
    sections = [p.section for p in ACTS_PROMPTS]
    assert len(sections) == len(set(sections))


def test_every_prompt_has_actual_text():
    for prompt in ACTS_PROMPTS:
        assert prompt.prompt.strip()
