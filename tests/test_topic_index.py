"""The curated topic list behind Topics mode - checked for shape, same as
`test_prayer_prompts.py`."""

from __future__ import annotations

from bible_tui.data.topic_index import TOPICS


def test_there_are_a_reasonable_number_of_topics():
    assert 15 <= len(TOPICS) <= 30


def test_topic_names_are_unique():
    names = [t.name for t in TOPICS]
    assert len(names) == len(set(names))


def test_every_topic_has_a_name_and_a_query():
    for topic in TOPICS:
        assert topic.name.strip()
        assert topic.query.strip()
